from django.contrib.auth.models import User as django_user
from django.core.urlresolvers import reverse
from mock.mock import MagicMock, patch, Mock
from rest_framework import status
from rest_framework.test import APITestCase
import json

from data.models import Workflow, WorkflowVersion, Job, JobFileStageGroup, JobError, \
    DDSUserCredential, DDSEndpoint, DDSJobInputFile, URLJobInputFile, JobOutputDir, \
    JobQuestionnaire, JobAnswerSet, VMFlavor, VMProject, JobToken, ShareGroup, DDSUser, \
    WorkflowMethodsDocument
from exceptions import WrappedDataServiceException
from util import DDSResource


class UserLogin(object):
    """
    Wraps up different user states for tests.
    """
    def __init__(self, client):
        self.client = client

    def become_unauthorized(self):
        self.client.logout()

    def become_normal_user(self):
        username = "user"
        password = "resu"
        user = django_user.objects.create_user(username=username, password=password)
        self.client.login(username=username, password=password)
        return user

    def become_other_normal_user(self):
        username = "user2"
        password = "resu2"
        user = django_user.objects.create_user(username=username, password=password)
        self.client.login(username=username, password=password)
        return user

    def become_admin_user(self):
        username = "myadmin"
        password = "nimda"
        user = django_user.objects.create_superuser(username=username, email='', password=password)
        self.client.login(username=username, password=password)
        return user


class DDSProjectsTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.user_login.become_normal_user()

    def testFailsUnauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('dds-projects-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('data.api.get_user_projects')
    def testListProjects(self, mock_get_user_projects):
        mock_get_user_projects.return_value = [Mock(id='abc123'), Mock(id='def567')]
        url = reverse('dds-projects-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    @patch('data.api.get_user_project')
    def testRetrieveProject(self, mock_get_user_project):
        project_id = 'abc123'
        mock_dds_project = Mock()
        # name is special on instantiation, so configure()
        mock_dds_project.configure_mock(id=project_id, name='ProjectA')
        mock_get_user_project.return_value = mock_dds_project
        url = reverse('dds-projects-list') + project_id + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'ProjectA')

    @patch('data.api.get_user_project')
    def testRetrieveProjectNotFound(self, mock_get_user_project):
        project_id = 'abc123'
        dds_error = MagicMock()
        dds_error.status_code = 404
        dds_error.message = 'Not Found'
        mock_get_user_project.side_effect = WrappedDataServiceException(dds_error)
        url = reverse('dds-projects-list') + project_id + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DDSResourcesTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.user_login.become_normal_user()

    def testFailsUnauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('dds-resources-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('data.api.get_user_project_content')
    def testListsResourcesByProject(self, mock_get_user_project_content):
        project_id = 'abc123'
        resource  = {'id': '12355','name': 'test.txt', 'project': {'id': project_id}, 'parent': {'kind': 'dds-project', 'id': project_id}}
        mock_get_user_project_content.return_value = DDSResource.from_list([resource])
        url = reverse('dds-resources-list')
        response = self.client.get(url, data={'project_id': project_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    @patch('data.api.get_user_folder_content')
    def testListsResourcesByFolder(self, mock_get_user_folder_content):
        project_id = 'abc123'
        folder_id = 'def456'
        resource = {'id': '12355', 'name': 'test.txt', 'project': {'id': project_id}, 'parent': {'kind': 'dds-folder', 'id': folder_id}}
        mock_get_user_folder_content.return_value = DDSResource.from_list([resource])
        url = reverse('dds-resources-list')
        response = self.client.get(url, data={'folder_id': folder_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    @patch('data.api.get_user_project_content')
    def testFailsWhenProjectNotFound(self, mock_get_user_project_content):
        project_id = 'abc123'
        dds_error = MagicMock()
        dds_error.status_code = 404
        dds_error.message = 'Not Found'
        mock_get_user_project_content.side_effect = WrappedDataServiceException(dds_error)
        url = reverse('dds-resources-list')
        response = self.client.get(url, data={'project_id': project_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testFailsWithoutProjectOrFolderID(self):
        url = reverse('dds-resources-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('data.api.get_user_project_content')
    def testIncludesFileDetailsForFiles(self, mock_get_user_project_content):
        project_id = 'abc123'
        file_resource = {
            'id': 'file2',
            'kind': 'dds-file',
            'name': 'file-with-details.txt',
            'project': {
                'id': project_id
            },
            'parent': {
                'kind': 'dds-project',
                'id': project_id
            },
            'current_version': {
                'id': 'v2',
                'version': 2,
                'upload': {
                    'id': 'u1',
                    'size': 1048576,
                }
            }
        }
        mock_get_user_project_content.return_value = DDSResource.from_list([file_resource])
        url = reverse('dds-resources-list')
        response = self.client.get(url, data={'project_id': project_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['version'], 2)
        self.assertEqual(response.data[0]['version_id'], 'v2')
        self.assertEqual(response.data[0]['size'], 1048576)

    @patch('data.api.get_user_project_content')
    def testDoesNotIncludeFileDetailsForFolders(self, mock_get_user_project_content):
        project_id = 'abc123'
        folder_resource = {
            'id': 'f2',
            'kind': 'dds-folder',
            'name': 'folder2',
            'project': {
                'id': project_id
            },
            'parent': {
                'kind': 'dds-project',
                'id': project_id
            }
        }
        mock_get_user_project_content.return_value = DDSResource.from_list([folder_resource])
        url = reverse('dds-resources-list')
        response = self.client.get(url, data={'project_id': project_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIsNone(response.data[0]['version'])
        self.assertIsNone(response.data[0]['version_id'])
        self.assertEqual(response.data[0]['size'], 0)


class DDSEndpointTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def testNoPermissionsWithoutAuth(self):
        self.user_login.become_unauthorized()
        url = reverse('ddsendpoint-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DDSUserCredentialTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret',
                                                   api_root='https://someserver.com/api')

    def testNoPermissionsWithoutAuth(self):
        self.user_login.become_unauthorized()
        url = reverse('ddsusercredential-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testUserOnlySeeAllCredsButNoTokens(self):
        """
        Normal users should not be able to see tokens but can pick from available credentials.
        """
        other_user = self.user_login.become_other_normal_user()
        user = self.user_login.become_normal_user()
        self.cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=user, token='secret1',
                                                    dds_id='1')
        self.cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=other_user, token='secret2',
                                                     dds_id='2')
        self.assertEqual(2, len(DDSUserCredential.objects.all()))

        url = reverse('ddsusercredential-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        self.assertEqual({'id': 1, 'user': 2, 'endpoint': 1}, response.data[0])
        self.assertEqual({'id': 2, 'user': 1, 'endpoint': 1}, response.data[1])

    def testUserCantCreate(self):
        user = self.user_login.become_normal_user()
        url = reverse('ddsusercredential-list')
        response = self.client.post(url, format='json', data={
            'endpoint': self.endpoint.id,
            'token': '12309ufwlkjasdf',
        })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class WorkflowTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def testNoPermissionsWithoutAuth(self):
        self.user_login.become_unauthorized()
        url = reverse('workflow-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testReadOnlyForAuthUser(self):
        self.user_login.become_normal_user()
        url = reverse('workflow-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(url, format='json', data={'name': 'RnaSeq'})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class WorkflowVersionTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def testNoPermissionsWithoutAuth(self):
        self.user_login.become_unauthorized()
        url = reverse('workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testReadOnlyForAuthUser(self):
        self.user_login.become_normal_user()
        url = reverse('workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testFilterByWorkflow(self):
        workflow1 = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        WorkflowVersion.objects.create(workflow=workflow1, version="1", url=cwl_url)
        workflow2 = Workflow.objects.create(name='RnaSeq2')
        WorkflowVersion.objects.create(workflow=workflow2, version="30", url=cwl_url)
        self.user_login.become_normal_user()
        url = reverse('workflowversion-list')

        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        response = self.client.get('{}?workflow={}'.format(url, workflow1.id), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        response = self.client.get('{}?workflow={}'.format(url, 202020), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class JobsTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')

    def testUserOnlySeeTheirData(self):
        url = reverse('job-list')
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='my job',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(normal_user.id, response.data[0]['user'])
        self.assertEqual('my job', response.data[0]['name'])
        self.assertEqual(self.workflow_version.id, response.data[0]['workflow_version'])

        other_user = self.user_login.become_other_normal_user()
        job = Job.objects.create(name='my job2',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb88',
                                 job_order={},
                                 user=other_user,
                                 share_group=self.share_group,
                                 )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(other_user.id, response.data[0]['user'])
        self.assertEqual(self.workflow_version.id, response.data[0]['workflow_version'])

    def testAdminSeeAllData(self):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='my job',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 )
        # normal user can't see admin endpoint
        url = reverse('admin_job-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        other_user = self.user_login.become_other_normal_user()
        job = Job.objects.create(name='my job2',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb88',
                                 job_order={},
                                 user=other_user,
                                 share_group=self.share_group,
                                 )
        # admin user can see both via admin endpoint
        admin_user = self.user_login.become_admin_user()
        url = reverse('admin_job-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        self.assertIn(other_user.id, [item['user']['id'] for item in response.data])
        self.assertIn(normal_user.id, [item['user']['id'] for item in response.data])
        self.assertIn('my job', [item['name'] for item in response.data])
        self.assertIn('my job2', [item['name'] for item in response.data])
        self.assertEqual(['RnaSeq', 'RnaSeq'], [item['workflow_version']['name'] for item in response.data])
        self.assertIn(self.share_group.id, [item['share_group'] for item in response.data])
        self.assertEqual([None, None], [item['user'].get('cleanup_job_vm') for item in response.data])

    def test_settings_effect_job_cleanup_vm(self):
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 )
        url = reverse('admin_job-list') + '{}/'.format(job.id)

        job.cleanup_vm = True
        job.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(True, response.data['cleanup_vm'])

        job.cleanup_vm = False
        job.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(False, response.data['cleanup_vm'])

    def testNormalUserSeeErrors(self):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 )
        JobError.objects.create(job=job, content='Err1', job_step='R')
        JobError.objects.create(job=job, content='Err2', job_step='R')
        url = reverse('job-list') + '{}/'.format(job.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_errors_content = [job_error['content'] for job_error in response.data['job_errors']]
        self.assertEqual(2, len(job_errors_content))
        self.assertIn('Err1', job_errors_content)
        self.assertIn('Err2', job_errors_content)

    def test_normal_user_trying_to_update_job(self):
        """
        Only admin should change job state or job step.
        Regular users can only change the state and step via the start, cancel and restart job endpoints.
        """
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 )
        url = reverse('admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                   data={
                                        'state': Job.JOB_STATE_FINISHED,
                                        'step': Job.JOB_STEP_RUNNING,
                                   })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def testAdminUserUpdatesStateAndStep(self):
        """
        Admin should be able to change job state and job step.
        """
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 )
        url = reverse('admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                    data={
                                        'state': Job.JOB_STATE_RUNNING,
                                        'step': Job.JOB_STEP_CREATE_VM,
                                    })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job = Job.objects.first()
        self.assertEqual(Job.JOB_STATE_RUNNING, job.state)
        self.assertEqual(Job.JOB_STEP_CREATE_VM, job.step)

    @patch('data.lando.LandoJob._make_client')
    def test_job_start(self, mock_make_client):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 )
        job.run_token = JobToken.objects.create(token='secret1')
        job.state = Job.JOB_STATE_AUTHORIZED
        job.save()
        url = reverse('job-list') + str(job.id) + '/start/'

        # Post to /start/ for job in NEW state should work
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['state'], Job.JOB_STATE_STARTING)

        # Post to /start/ for job in RUNNING state should fail
        job.state = Job.JOB_STATE_RUNNING
        job.save()
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('data.lando.LandoJob._make_client')
    def test_job_cancel(self, mock_make_client):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/cancel/'
        # Post to /cancel/ for job should work
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['state'], Job.JOB_STATE_CANCELING)

    @patch('data.lando.LandoJob._make_client')
    def test_job_restart(self, mock_make_client):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/restart/'

        # Post to /restart/ for job in NEW state should fail (user should use /start/)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_make_client().restart_job.assert_not_called()

        # Post to /restart/ for job in ERROR state should work
        job.state = Job.JOB_STATE_ERROR
        job.save()
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['state'], Job.JOB_STATE_RESTARTING)
        mock_make_client().restart_job.assert_called_with(str(1))

        # Post to /restart/ for job in CANCEL state should work
        job.state = Job.JOB_STATE_CANCEL
        job.save()
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_normal_user_trying_create_job_directly(self):
        url = reverse('job-list')
        normal_user = self.user_login.become_normal_user()
        response = self.client.post(url, format='json',
                                    data={
                                        'name': 'my job',
                                        'workflow_version': self.workflow_version.id,
                                        'vm_project_name': 'jpb67',
                                        'job_order': '{}',
                                    })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_authorize_without_token(self):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing required token field.')

    def test_authorize_with_fake_token(self):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url, format='json', data={'token': 'secret1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'This is not a valid token.')

    def test_authorize_with_good_token(self):
        job_token = JobToken.objects.create(token='secret1')
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url, format='json', data={'token': 'secret1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['job']['id'], job.id)

    def test_authorize_with_good_token_but_bad_state(self):
        job_token = JobToken.objects.create(token='secret1')
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 state=Job.JOB_STATE_RUNNING,
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url, format='json', data={'token': 'secret1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Job state must be NEW.')

    def test_authorize_with_already_used_token(self):
        normal_user = self.user_login.become_normal_user()
        job_token = JobToken.objects.create(token='secret1')
        earlier_job = Job.objects.create(workflow_version=self.workflow_version,
                                         vm_project_name='jpb67',
                                         job_order={},
                                         user=normal_user,
                                         stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                         run_token=job_token,
                                         share_group=self.share_group,
                                         )
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 vm_project_name='jpb67',
                                 job_order={},
                                 user=normal_user,
                                 stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                 share_group=self.share_group,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url, format='json', data={'token': 'secret1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'This token has already been used.')

    def test_delete_job(self):
        normal_user = self.user_login.become_normal_user()
        values = [
            # job state         expected response status code
            (Job.JOB_STATE_NEW, status.HTTP_204_NO_CONTENT),
            (Job.JOB_STATE_AUTHORIZED, status.HTTP_204_NO_CONTENT),
            (Job.JOB_STATE_STARTING, status.HTTP_400_BAD_REQUEST),
            (Job.JOB_STATE_RUNNING, status.HTTP_400_BAD_REQUEST),
            (Job.JOB_STATE_FINISHED, status.HTTP_400_BAD_REQUEST),
            (Job.JOB_STATE_ERROR, status.HTTP_400_BAD_REQUEST),
            (Job.JOB_STATE_CANCELING, status.HTTP_400_BAD_REQUEST),
            (Job.JOB_STATE_CANCEL, status.HTTP_400_BAD_REQUEST),
            (Job.JOB_STATE_RESTARTING, status.HTTP_400_BAD_REQUEST),
        ]
        for job_state, expected_response_status_code in values:
            job = Job.objects.create(workflow_version=self.workflow_version,
                                     vm_project_name='jpb67',
                                     job_order={},
                                     user=normal_user,
                                     stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                     share_group=self.share_group,
                                     )
            job.state = job_state
            job.save()
            url = reverse('job-list') + str(job.id) + '/'
            response = self.client.delete(url)
            self.assertEqual(response.status_code, expected_response_status_code)


class JobStageGroupTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')

    def testOnlySeeOwnStageGroups(self):
        other_user = self.user_login.become_normal_user()
        other_stage_group = JobFileStageGroup.objects.create(user=other_user)
        other_job = Job.objects.create(workflow_version=self.workflow_version,
                                       vm_project_name='test',
                                       job_order='{}',
                                       user=other_user,
                                       stage_group=other_stage_group,
                                       share_group=self.share_group,
                                       )
        this_user = self.user_login.become_other_normal_user()
        this_stage_group = JobFileStageGroup.objects.create(user=this_user)
        this_job = Job.objects.create(workflow_version=self.workflow_version,
                                      vm_project_name='test',
                                      job_order='{}',
                                      user=this_user,
                                      stage_group=this_stage_group,
                                      share_group=self.share_group,
                                      )
        # User endpoint only shows current user's data
        url = reverse('jobfilestagegroup-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))

        # Admin endpoint shows all user's data
        self.user_login.become_admin_user()
        url = reverse('admin_jobfilestagegroup-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))

    def testAutoFillsInUser(self):
        url = reverse('jobfilestagegroup-list')
        normal_user = self.user_login.become_normal_user()
        response = self.client.post(url, format='json',
                                    data={})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        stage_group = JobFileStageGroup.objects.first()
        self.assertEqual(stage_group.user, normal_user)


class JobErrorTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')

    def testNormalUserReadOnly(self):
        other_user = self.user_login.become_normal_user()
        other_job = Job.objects.create(workflow_version=self.workflow_version,
                                       vm_project_name='test',
                                       job_order='{}',
                                       user=other_user,
                                       share_group=self.share_group,
                                       )
        JobError.objects.create(job=other_job, content='Out of memory.', job_step=Job.JOB_STEP_RUNNING)
        # Normal user can't write
        url = reverse('joberror-list')
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        my_user = self.user_login.become_other_normal_user()
        my_job = Job.objects.create(workflow_version=self.workflow_version,
                                    vm_project_name='test',
                                    job_order='{}',
                                    user=my_user,
                                    share_group=self.share_group,
                                    )
        JobError.objects.create(job=my_job, content='Out of memory.', job_step=Job.JOB_STEP_RUNNING)

        # User endpoint only shows current user's data
        url = reverse('joberror-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))

        # Admin endpoint shows all user's data
        self.user_login.become_admin_user()
        url = reverse('admin_joberror-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))

    def testNormalEndpointNoWrite(self):
        self.user_login.become_normal_user()
        url = reverse('joberror-list')
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testAdminEndpointCanWrite(self):
        my_user = self.user_login.become_admin_user()
        my_job = Job.objects.create(workflow_version=self.workflow_version,
                                    vm_project_name='test',
                                    job_order='{}',
                                    user=my_user,
                                    share_group=self.share_group,
                                    )
        url = reverse('admin_joberror-list')
        response = self.client.post(url, format='json', data={
            'job': my_job.id,
            'content': 'oops',
            'job_step': Job.JOB_STEP_CREATE_VM,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, len(JobError.objects.all()))


class DDSJobInputFileTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.other_user = self.user_login.become_other_normal_user()
        self.my_user = self.user_login.become_normal_user()
        self.stage_group = JobFileStageGroup.objects.create(user=self.my_user)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.my_job = Job.objects.create(workflow_version=self.workflow_version,
                                         vm_project_name='test',
                                         job_order='{}',
                                         user=self.my_user,
                                         stage_group=self.stage_group,
                                         share_group=self.share_group)
        endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret', api_root='https://someserver.com/api')
        self.cred = DDSUserCredential.objects.create(endpoint=endpoint, user=self.my_user, token='secret2', dds_id='1')
        self.other_cred = DDSUserCredential.objects.create(endpoint=endpoint, user=self.other_user, token='secret3',
                                                           dds_id='2')

    def testPostAndRead(self):
        url = reverse('ddsjobinputfile-list')
        response = self.client.post(url, format='json', data={
            'stage_group': self.stage_group.id,
            'project_id': '12356',
            'file_id': '345987',
            'dds_user_credentials': self.cred.id,
            'destination_path': 'data.txt',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, len(DDSJobInputFile.objects.all()))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual('data.txt', response.data[0]['destination_path'])

    def testUsingOthersCreds(self):
        url = reverse('ddsjobinputfile-list')
        response = self.client.post(url, format='json', data={
            'stage_group': self.stage_group.id,
            'project_id': '12356',
            'file_id': '345987',
            'dds_user_credentials': self.other_cred.id,
            'destination_path': 'data.txt',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testLargeFileSize(self):
        url = reverse('ddsjobinputfile-list')
        response = self.client.post(url, format='json', data={
            'stage_group': self.stage_group.id,
            'project_id': '654321',
            'file_id': '212121',
            'dds_user_credentials': self.other_cred.id,
            'destination_path': 'data.txt',
            'size': 8 * 1024 * 1024 * 1024
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class URLJobInputFileTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.my_user = self.user_login.become_normal_user()
        self.stage_group = JobFileStageGroup.objects.create(user=self.my_user)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.my_job = Job.objects.create(workflow_version=self.workflow_version,
                                         vm_project_name='test',
                                         job_order='{}',
                                         user=self.my_user,
                                         stage_group=self.stage_group,
                                         share_group=self.share_group,
                                         )

    def testPostAndRead(self):
        url = reverse('urljobinputfile-list')
        response = self.client.post(url, format='json', data={
            'stage_group': self.stage_group.id,
            'url': 'http://stuff.com/data.txt',
            'destination_path': 'data.txt',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, len(URLJobInputFile.objects.all()))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual('http://stuff.com/data.txt', response.data[0]['url'])

    def testLargeFileSize(self):
        url = reverse('urljobinputfile-list')
        response = self.client.post(url, format='json', data={
            'stage_group': self.stage_group.id,
            'url': 'http://stuff.com/data.txt',
            'destination_path': 'data.txt',
            'size': 8 * 1024 * 1024 * 1024
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class JobOutputDirTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.other_user = self.user_login.become_other_normal_user()
        self.my_user = self.user_login.become_normal_user()
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.my_job = Job.objects.create(workflow_version=self.workflow_version,
                                         vm_project_name='test',
                                         job_order='{}',
                                         user=self.my_user,
                                         share_group=self.share_group,
                                         )
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret', api_root='https://someserver.com/api')
        self.cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=self.my_user, token='secret2',
                                                     dds_id='1')
        self.others_cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=self.other_user,
                                                            token='secret3', dds_id='2')

    def test_list_dirs(self):
        JobOutputDir.objects.create(job=self.my_job, dir_name='results', project_id='1',
                                    dds_user_credentials=self.cred)
        url = reverse('joboutputdir-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        job_output_dir = response.data[0]
        self.assertEqual(self.my_job.id, job_output_dir['job'])
        self.assertEqual('results', job_output_dir['dir_name'])
        self.assertEqual('1', job_output_dir['project_id'])
        self.assertEqual(self.cred.id, job_output_dir['dds_user_credentials'])

    def test_create(self):
        url = reverse('joboutputdir-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'dir_name': 'results',
            'project_id': '123',
            'dds_user_credentials': self.cred.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_output_dir = JobOutputDir.objects.first()
        self.assertEqual(self.my_job, job_output_dir.job)
        self.assertEqual('results', job_output_dir.dir_name)
        self.assertEqual('123', job_output_dir.project_id)
        self.assertEqual(self.cred, job_output_dir.dds_user_credentials)

    def test_can_use_others_creds(self):
        url = reverse('joboutputdir-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'dir_name': 'results',
            'project_id': '123',
            'dds_user_credentials': self.others_cred.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_dirs_admin(self):
        # Admin can list other users job-output-directories
        JobOutputDir.objects.create(job=self.my_job, dir_name='results', project_id='1',
                                    dds_user_credentials=self.cred)
        self.user_login.become_admin_user()
        url = reverse('admin_joboutputdir-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        job_output_dir = response.data[0]
        self.assertEqual(self.my_job.id, job_output_dir['job'])
        self.assertEqual('results', job_output_dir['dir_name'])
        self.assertEqual('1', job_output_dir['project_id'])
        self.assertEqual(self.cred.id, job_output_dir['dds_user_credentials'])

    def test_create_admin(self):
        # Admin can create other users job-output-directories
        self.user_login.become_admin_user()
        url = reverse('admin_joboutputdir-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'dir_name': 'results',
            'project_id': '123',
            'dds_user_credentials': self.cred.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_output_dir = JobOutputDir.objects.first()
        self.assertEqual(self.my_job, job_output_dir.job)
        self.assertEqual('results', job_output_dir.dir_name)
        self.assertEqual('123', job_output_dir.project_id)
        self.assertEqual(self.cred, job_output_dir.dds_user_credentials)


class JobQuestionnaireTestCase(APITestCase):
    def setUp(self):
        """
        Create two questionnaires since this should be a read only endpoint.
        """
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.system_job_order_json1 = json.dumps({'system_input': 1})
        self.system_job_order_json2 = json.dumps({'system_input': 2})
        self.flavor = VMFlavor.objects.create(name='flavor1')
        self.project = VMProject.objects.create(name='bespin-project')
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.questionnaire1 = JobQuestionnaire.objects.create(name='Workflow1',
                                                              description='A really large workflow',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json1,
                                                              vm_flavor=self.flavor,
                                                              vm_project=self.project,
                                                              share_group=self.share_group,
                                                              )
        self.questionnaire2 = JobQuestionnaire.objects.create(name='Workflow2',
                                                              description='A rather small workflow',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json2,
                                                              vm_flavor = self.flavor,
                                                              vm_project = self.project,
                                                              share_group=self.share_group,
                                                              )
        self.questionnaire2.save()

    def test_user_can_read(self):
        self.user_login.become_normal_user()
        url = reverse('jobquestionnaire-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))

        url = '{}{}/'.format(reverse('jobquestionnaire-list'), self.questionnaire1.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('Workflow1', response.data['name'])
        self.assertEqual('A really large workflow', response.data['description'])
        self.assertEqual(self.workflow_version.id, response.data['workflow_version'])
        self.assertEqual(self.system_job_order_json1, response.data['system_job_order_json'])
        self.assertEqual(self.flavor.id, response.data['vm_flavor'])
        self.assertEqual(self.project.id, response.data['vm_project'])

        url = '{}{}/'.format(reverse('jobquestionnaire-list'), self.questionnaire2.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('Workflow2', response.data['name'])
        self.assertEqual('A rather small workflow', response.data['description'])
        self.assertEqual(self.workflow_version.id, response.data['workflow_version'])
        self.assertEqual(self.system_job_order_json2, response.data['system_job_order_json'])
        self.assertEqual(self.flavor.id, response.data['vm_flavor'])
        self.assertEqual(self.project.id, response.data['vm_project'])

    def test_user_cant_write(self):
        self.user_login.become_normal_user()
        url = reverse('jobquestionnaire-list')
        response = self.client.post(url, format='json', data={
            'description': 'Workflow3',
            'workflow_version': self.workflow_version.id
        })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        questionnaire1_endpoint = '{}{}/'.format(url, self.questionnaire1.id)
        response = self.client.put(questionnaire1_endpoint, format='json', data={
            'description': 'Workflow3',
            'workflow_version': self.workflow_version.id
        })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class JobAnswerSetTests(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.flavor = VMFlavor.objects.create(name='flavor1')
        self.project = VMProject.objects.create(name='bespin-project')
        self.system_job_order_json1 = json.dumps({'system_input': 1})
        self.system_job_order_json2 = json.dumps({'system_input': 2})
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.questionnaire1 = JobQuestionnaire.objects.create(description='Workflow1',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json1,
                                                              vm_flavor=self.flavor,
                                                              vm_project=self.project,
                                                              share_group=self.share_group
                                                              )
        self.questionnaire2 = JobQuestionnaire.objects.create(description='Workflow1',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json2,
                                                              vm_flavor=self.flavor,
                                                              vm_project=self.project,
                                                              share_group=self.share_group
                                                              )
        self.other_user = self.user_login.become_other_normal_user()
        self.user = self.user_login.become_normal_user()
        self.stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret',
                                                   api_root='https://someserver.com/api')
        self.user_job_order_json1 = json.dumps({'input1': 'value1'})
        self.user_job_order_json2 = json.dumps({'input1': 'value1', 'input2': [1, 2, 3]})

    def test_user_crud(self):
        url = reverse('jobanswerset-list')
        response = self.client.post(url, format='json', data={
            'questionnaire': self.questionnaire1.id,
            'job_name': 'Test job 1',
            'user_job_order_json' : self.user_job_order_json1,
            'stage_group' : self.stage_group.id,
            'fund_code': '123-4'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, len(JobAnswerSet.objects.all()))
        job_answer_set = JobAnswerSet.objects.first()
        self.assertEqual(job_answer_set.user_job_order_json, self.user_job_order_json1)

        url = '{}{}/'.format(reverse('jobanswerset-list'), response.data['id'])
        response = self.client.put(url, format='json', data={
            'questionnaire': self.questionnaire1.id,
            'job_name': 'Test job 2',
            'user_job_order_json': self.user_job_order_json2,
            'stage_group': self.stage_group.id,
            'fund_code': '123-5'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_answer_set = JobAnswerSet.objects.first()
        self.assertEqual(job_answer_set.user_job_order_json, self.user_job_order_json2)
        self.assertEqual(job_answer_set.fund_code, '123-5')

        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(0, len(JobAnswerSet.objects.all()))

    def setup_minimal_questionnaire(self):
        # user_cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=self.user, token='secret2',
        #                                              dds_id='1')
        questionnaire = JobQuestionnaire.objects.create(description='Workflow1',
                                                        workflow_version=self.workflow_version,
                                                        system_job_order_json=self.system_job_order_json1,
                                                        vm_flavor=self.flavor,
                                                        vm_project=self.project,
                                                        share_group=self.share_group
                                                        )
        return questionnaire

    def test_create_job_with_items(self):
        questionnaire = self.setup_minimal_questionnaire()
        url = reverse('jobanswerset-list')
        response = self.client.post(url, format='json', data={
            'questionnaire': questionnaire.id,
            'job_name': 'Test job with items',
            'user_job_order_json': self.user_job_order_json1,
            'stage_group': self.stage_group.id,
            'fund_code': '123-5'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_answer_set_id = response.data['id']
        url = reverse('jobanswerset-list') + str(job_answer_set_id) + "/create-job/"
        response = self.client.post(url, format='json', data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual('Test job with items', response.data['name'])
        self.assertEqual(self.flavor.name, response.data['vm_flavor'])
        self.assertEqual(self.project.name, response.data['vm_project_name'])
        self.assertEqual('123-5', response.data['fund_code'])
        expected_job_order = json.loads(self.system_job_order_json1).copy()
        expected_job_order.update(json.loads(self.user_job_order_json1))
        self.assertEqual(json.dumps(expected_job_order), response.data['job_order'])
        self.assertEqual(1, len(Job.objects.all()))
        self.assertEqual(1, len(JobOutputDir.objects.all()))

    @patch('data.jobfactory.JobOutputDir')
    def test_create_job_with_exception_rolls_back(self, MockJobOutputDir):
        MockJobOutputDir.objects.create.side_effect = ValueError("oops")
        questionnaire = self.setup_minimal_questionnaire()
        url = reverse('jobanswerset-list')
        response = self.client.post(url, format='json', data={
            'questionnaire': questionnaire.id,
            'job_name': 'Test job with items',
            'user_job_order_json': self.user_job_order_json1,
            'stage_group': self.stage_group.id,
            'volume_size': 200
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_answer_set_id = response.data['id']
        url = reverse('jobanswerset-list') + str(job_answer_set_id) + "/create-job/"
        with self.assertRaises(ValueError):
            self.client.post(url, format='json', data={})
        self.assertEqual(0, len(Job.objects.all()))


class AdminJobTokensTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_only_allow_admin_users(self):
        url = reverse('admin_jobtoken-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list(self):
        self.user_login.become_admin_user()
        url = reverse('admin_jobtoken-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
        JobToken.objects.create(token='one')
        JobToken.objects.create(token='two')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([x['token'] for x in response.data], ['one', 'two'])

    def test_create(self):
        self.user_login.become_admin_user()
        url = reverse('admin_jobtoken-list')
        response = self.client.post(url, format='json', data={
            'token': 'secret1'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(url, format='json', data={
            'token': 'secret2'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(url, format='json', data={
            'token': 'secret1'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminShareGroupTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_admin_only_allow_admin_users(self):
        url = reverse('admin_sharegroup-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_list(self):
        dds_user1 = DDSUser.objects.create(name='Joe', dds_id='123')
        dds_user2 = DDSUser.objects.create(name='Jim', dds_id='456')
        dds_user3 = DDSUser.objects.create(name='Bob', dds_id='789')
        share_group1 = ShareGroup.objects.create(name='Data validation team 1')
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        share_group2 = ShareGroup.objects.create(name='Data validation team 2')
        share_group2.users = [dds_user1, dds_user3]
        share_group2.save()

        url = reverse('admin_sharegroup-list')
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        group = response.data[0]
        self.assertEqual('Data validation team 1', group['name'])
        group_users = [group_user['dds_id'] for group_user in group['users']]
        self.assertEqual(['123','456'], group_users)
        group = response.data[1]
        self.assertEqual('Data validation team 2', group['name'])
        group_users = [group_user['dds_id'] for group_user in group['users']]
        self.assertEqual(['123','789'], group_users)

    def test_admin_read_single_group(self):
        # Test that we can read a single group (so we can share results with the group members)
        dds_user1 = DDSUser.objects.create(name='Joe', dds_id='123')
        dds_user2 = DDSUser.objects.create(name='Jim', dds_id='456')
        share_group1 = ShareGroup.objects.create(name='Data validation team 1')
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        url = reverse('admin_sharegroup-list') + "{}/".format(share_group1.id)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group = response.data
        self.assertEqual('Data validation team 1', group['name'])
        group_users = [group_user['dds_id'] for group_user in group['users']]
        self.assertEqual(['123','456'], group_users)

    def test_user_only_allow_auth_or_admin_users(self):
        url = reverse('sharegroup-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_list(self):
        dds_user1 = DDSUser.objects.create(name='Joe', dds_id='123')
        dds_user2 = DDSUser.objects.create(name='Jim', dds_id='456')
        dds_user3 = DDSUser.objects.create(name='Bob', dds_id='789')
        share_group1 = ShareGroup.objects.create(name='Data validation team 1')
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        share_group2 = ShareGroup.objects.create(name='Data validation team 2')
        share_group2.users = [dds_user1, dds_user3]
        share_group2.save()

        url = reverse('sharegroup-list')
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        group = response.data[0]
        self.assertEqual('Data validation team 1', group['name'])
        self.assertEqual(None, group.get('users'))  # Regular users cannot see users in groups
        group = response.data[1]
        self.assertEqual('Data validation team 2', group['name'])
        self.assertEqual(None, group.get('users'))  # Regular users cannot see users in groups

    def test_user_read_single_group(self):
        # Test that we can read a single group (so we can share results with the group members)
        dds_user1 = DDSUser.objects.create(name='Joe', dds_id='123')
        dds_user2 = DDSUser.objects.create(name='Jim', dds_id='456')
        share_group1 = ShareGroup.objects.create(name='Data validation team 1')
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        url = reverse('sharegroup-list') + "{}/".format(share_group1.id)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group = response.data
        self.assertEqual('Data validation team 1', group['name'])
        self.assertEqual(None, group.get('users'))  # Regular users cannot see users in groups


class WorkflowMethodsDocumentTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow1 = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow1, version="1", url=cwl_url)
        self.methods_document = WorkflowMethodsDocument.objects.create(workflow_version=self.workflow_version,
                                                                       content="#One")

    def test_cannot_write(self):
        self.user_login.become_normal_user()
        url = reverse('workflowmethodsdocument-list')
        response = self.client.post(url, format='json', data={
            'workflow_version': self.workflow_version.id,
            'content': '#Two',
        })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.user_login.become_admin_user()
        url = reverse('admin_workflowmethodsdocument-list')
        response = self.client.post(url, format='json', data={
            'workflow_version': self.workflow_version.id,
            'content': '#Two',
        })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_read_only_access(self):
        url = reverse('workflowmethodsdocument-list')
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual('#One', response.data[0]['content'])

        url = reverse('admin_workflowmethodsdocument-list')
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual('#One', response.data[0]['content'])
