from django.contrib.auth.models import User as django_user
from django.core.urlresolvers import reverse, NoReverseMatch
from django.test import override_settings
from unittest.mock import MagicMock, patch, Mock
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework import ISO_8601
import json
import datetime

from data.models import Workflow, WorkflowVersion, Job, JobFileStageGroup, JobError, \
    DDSUserCredential, DDSEndpoint, DDSJobInputFile, URLJobInputFile, JobDDSOutputProject, \
    JobQuestionnaire, JobAnswerSet, JobFlavor, VMProject, JobToken, ShareGroup, DDSUser, \
    WorkflowMethodsDocument, EmailMessage, EmailTemplate, JobSettings, \
    JobQuestionnaireType
from data.tests_models import create_vm_job_settings
from rest_framework.authtoken.models import Token
from data.exceptions import WrappedDataServiceException
from data.util import DDSResource


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
        cred1 = DDSUserCredential.objects.create(endpoint=self.endpoint, user=user, token='secret1', dds_id='1')
        cred2 = DDSUserCredential.objects.create(endpoint=self.endpoint, user=other_user, token='secret2', dds_id='2')
        self.assertEqual(2, len(DDSUserCredential.objects.all()))

        url = reverse('ddsusercredential-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        self.assertEqual({'id': cred1.id, 'user': user.id, 'endpoint': self.endpoint.id, 'dds_id':'1'},
                         response.data[0])
        self.assertEqual({'id': cred2.id, 'user': other_user.id, 'endpoint': self.endpoint.id, 'dds_id':'2'},
                         response.data[1])

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

    def testFilterBySlug(self):
        Workflow.objects.create(name='workflow1', tag='one')
        Workflow.objects.create(name='workflow2', tag='two')
        Workflow.objects.create(name='workflow3', tag='three')
        self.user_login.become_normal_user()
        url = reverse('workflow-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        url = reverse('workflow-list') + "?tag=two"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'workflow2')


class WorkflowVersionTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')

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
        workflow1 = Workflow.objects.create(name='RnaSeq', tag='rnaseq1')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        WorkflowVersion.objects.create(workflow=workflow1, version="1", url=cwl_url, fields=[])
        workflow2 = Workflow.objects.create(name='RnaSeq2', tag='rnaseq2')
        WorkflowVersion.objects.create(workflow=workflow2, version="30", url=cwl_url, fields=[])
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

    def test_get_response_questionnaires_array(self):
        self.user_login.become_normal_user()
        workflow1 = Workflow.objects.create(name='RnaSeq', tag='rnaseq1')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/" \
                  "predict-workflow-packed.cwl"
        wfv = WorkflowVersion.objects.create(workflow=workflow1, version="1", url=cwl_url, fields=[])
        questionnaire_type = JobQuestionnaireType.objects.create(tag='human')
        questionnaire1 = JobQuestionnaire.objects.create(name='Workflow1',
                                                         description='A really large workflow',
                                                         workflow_version=wfv,
                                                         system_job_order_json={},
                                                         share_group=self.share_group,
                                                         job_settings=self.job_settings,
                                                         job_flavor=self.job_flavor,
                                                         type=questionnaire_type
                                                         )
        url = reverse('workflowversion-list') + '{}/'.format(wfv.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['url'], cwl_url)
        self.assertEqual(response.data['questionnaires'], [questionnaire1.id])

    def test_filter_by_enable_ui(self):
        workflow1 = Workflow.objects.create(name='RnaSeq', tag='rnaseq1')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        WorkflowVersion.objects.create(workflow=workflow1, version="1", url=cwl_url, fields=[], enable_ui=True)
        workflow2 = Workflow.objects.create(name='RnaSeq2', tag='rnaseq2')
        WorkflowVersion.objects.create(workflow=workflow2, version="30", url=cwl_url, fields=[], enable_ui=False)
        self.user_login.become_normal_user()
        url = reverse('workflowversion-list')

        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['enable_ui'] for item in response.data]), set([True, False]))

        response = self.client.get('{}?enable_ui={}'.format(url, 'true'), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['enable_ui'], True)

        response = self.client.get('{}?enable_ui={}'.format(url, 'false'), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['enable_ui'], False)


def add_job_settings(obj, project_name='project1',
                    cloud_name='cloud1',
                    settings_name='settings1'):
    vm_project = VMProject.objects.create(name=project_name)
    obj.job_settings = create_vm_job_settings(name=settings_name, vm_project=vm_project, cloud_name=cloud_name)


class JobsTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.job_flavor = JobFlavor.objects.create(name='flavor1')
        add_job_settings(self)

    def testUserOnlySeeTheirData(self):
        url = reverse('job-list')
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='my job',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(normal_user.id, response.data[0]['user'])
        self.assertEqual('my job', response.data[0]['name'])
        self.assertEqual(self.workflow_version.id, response.data[0]['workflow_version'])
        self.assertEqual(self.job_settings.id, response.data[0]['vm_settings'])

        other_user = self.user_login.become_other_normal_user()
        job = Job.objects.create(name='my job2',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=other_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(other_user.id, response.data[0]['user'])
        self.assertEqual(self.workflow_version.id, response.data[0]['workflow_version'])
        self.assertEqual(self.job_settings.id, response.data[0]['vm_settings'])

    def testUserCannotSeeDeletedJob(self):
        url = reverse('job-list')
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='my job',
                                 state=Job.JOB_STATE_NEW,
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))

        # Now mark as deleted
        job.state = Job.JOB_STATE_DELETED
        job.save()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(0, len(response.data))

    def testAdminSeeAllData(self):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='my job',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        # normal user can't see admin endpoint
        url = reverse('admin_job-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        other_user = self.user_login.become_other_normal_user()
        job = Job.objects.create(name='my job2',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=other_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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

    def testAdminCanSeeDeletedJob(self):
        url = reverse('admin_job-list')
        normal_user = self.user_login.become_normal_user()
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='my job',
                                 state=Job.JOB_STATE_NEW,
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))

        # Now mark as deleted
        job.state = Job.JOB_STATE_DELETED
        job.save()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(response.data[0]['state'], 'D')

    def testAdminFilterJobsVmInstanceName(self):
        admin_user = self.user_login.become_admin_user()
        Job.objects.create(name='somejob',
                           workflow_version=self.workflow_version,
                           vm_instance_name='vm_job_1',
                           job_order={},
                           user=admin_user,
                           share_group=self.share_group,
                           job_settings=self.job_settings,
                           job_flavor=self.job_flavor,
                           )
        Job.objects.create(name='somejob2',
                           workflow_version=self.workflow_version,
                           vm_instance_name='vm_job_2',
                           job_order={},
                           user=admin_user,
                           share_group=self.share_group,
                           job_settings=self.job_settings,
                           job_flavor=self.job_flavor,
                           )
        url = reverse('admin_job-list') + '?vm_instance_name=vm_job_1'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual('somejob', response.data[0]['name'])

    def test_settings_effect_job_cleanup_vm(self):
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                   data={
                                        'state': Job.JOB_STATE_FINISHED,
                                        'step': Job.JOB_STEP_RUNNING,
                                   })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('data.api.JobMailer')
    def testAdminUserUpdatesStateAndStep(self, MockJobMailer):
        """
        Admin should be able to change job state and job step.
        """
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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

    @patch('data.api.JobMailer')
    def test_mails_when_job_state_changes(self, MockJobMailer):
        mock_mail_current_state = Mock()
        MockJobMailer.return_value.mail_current_state = mock_mail_current_state
        """
        Admin should be able to change job state and job step.
        """
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 state=Job.JOB_STATE_AUTHORIZED,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                    data={
                                        'state': Job.JOB_STATE_RUNNING,
                                        'step': Job.JOB_STEP_CREATE_VM,
                                    })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_mail_current_state.called)

    @patch('data.api.JobMailer')
    def test_does_not_mail_when_job_state_stays(self, MockJobMailer):
        mock_mail_current_state = Mock()
        MockJobMailer.return_value.mail_current_state = mock_mail_current_state
        """
        Admin should be able to change job state and job step.
        """
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 state=Job.JOB_STATE_RUNNING,
                                 step=Job.JOB_STEP_CREATE_VM,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                    data={
                                        'state': Job.JOB_STATE_RUNNING,
                                        'step': Job.JOB_STEP_RUNNING,
                                    })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(mock_mail_current_state.called)

    @patch('data.lando.LandoJob._make_client')
    def test_job_start(self, mock_make_client):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
        mock_make_client().restart_job.assert_called_with(str(job.id))

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
                                        'vm_settings': self.job_settings.id,
                                        'job_order': '{}',
                                    })
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_authorize_without_token(self):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing required token field.')

    def test_authorize_with_fake_token(self):
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
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
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 state=Job.JOB_STATE_RUNNING,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url, format='json', data={'token': 'secret1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Job state must be NEW.')

    def test_authorize_with_already_used_token(self):
        normal_user = self.user_login.become_normal_user()
        job_token = JobToken.objects.create(token='secret1')
        earlier_job = Job.objects.create(workflow_version=self.workflow_version,
                                         job_order={},
                                         user=normal_user,
                                         stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                         run_token=job_token,
                                         share_group=self.share_group,
                                         job_settings=self.job_settings,
                                         job_flavor=self.job_flavor,
                                         )
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('job-list') + str(job.id) + '/authorize/'
        response = self.client.post(url, format='json', data={'token': 'secret1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'This token has already been used.')

    def test_delete_job(self):
        normal_user = self.user_login.become_normal_user()
        values = [
            # job state         expected response status code       0=pretend, 1=really delete
            (Job.JOB_STATE_NEW, status.HTTP_204_NO_CONTENT, 0),
            (Job.JOB_STATE_AUTHORIZED, status.HTTP_204_NO_CONTENT, 0),
            (Job.JOB_STATE_STARTING, status.HTTP_400_BAD_REQUEST, 1),
            (Job.JOB_STATE_RUNNING, status.HTTP_400_BAD_REQUEST, 1),
            (Job.JOB_STATE_FINISHED, status.HTTP_204_NO_CONTENT, 1),
            (Job.JOB_STATE_ERROR, status.HTTP_204_NO_CONTENT, 1),
            (Job.JOB_STATE_CANCELING, status.HTTP_400_BAD_REQUEST, 1),
            (Job.JOB_STATE_CANCEL, status.HTTP_204_NO_CONTENT, 1),
            (Job.JOB_STATE_RESTARTING, status.HTTP_400_BAD_REQUEST, 1),
        ]
        for job_state, expected_response_status_code, expected_count in values:
            job = Job.objects.create(workflow_version=self.workflow_version,
                                     job_order={},
                                     user=normal_user,
                                     stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                     share_group=self.share_group,
                                     job_settings=self.job_settings,
                                     job_flavor=self.job_flavor,
                                     )
            job_id = job.id
            job.state = job_state
            job.save()
            url = reverse('job-list') + str(job_id) + '/'
            response = self.client.delete(url)
            self.assertEqual(response.status_code, expected_response_status_code)
            self.assertEqual(Job.objects.filter(id=job_id).count(), expected_count)

    def test_job_includes_run_token(self):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 stage_group=JobFileStageGroup.objects.create(user=normal_user),
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        run_token = JobToken.objects.create(token='test-token')
        job.run_token = run_token;
        job.save()
        url = reverse('job-list') + '{}/'.format(job.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['run_token'], 'test-token')

    @patch('data.api.JobUsage')
    def test_job_usage(self, mock_job_usage):
        mock_job_usage.return_value.vm_hours = 1.2
        normal_user = self.user_login.become_normal_user()
        stage_group = JobFileStageGroup.objects.create(user=normal_user)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 stage_group=stage_group,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('job-list') + str(job.id) + '/live-usage/'
        # Post to /cancel/ for job should work
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vm_hours'], 1.2)

    @patch('data.serializers.JobUsage')
    def test_usage_included_in_jobs_list(self, mock_job_usage):
        mock_job_usage.return_value.vm_hours = 1.2
        mock_job_usage.return_value.cpu_hours = 1.2
        url = reverse('job-list')
        normal_user = self.user_login.become_normal_user()
        job1 = Job.objects.create(name='job1',
                                  workflow_version=self.workflow_version,
                                  job_order={},
                                  user=normal_user,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  state=Job.JOB_STATE_FINISHED
                                  )
        job2 = Job.objects.create(name='job2',
                                  workflow_version=self.workflow_version,
                                  job_order={},
                                  user=normal_user,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  state=Job.JOB_STATE_RUNNING
                                  )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        self.assertEqual(response.data[0]['id'], job1.id)
        self.assertEqual(response.data[0]['usage'], {'cpu_hours': 1.2, 'vm_hours': 1.2})
        self.assertEqual(response.data[1]['id'], job2.id)
        self.assertEqual(response.data[1]['usage'], None)


class JobStageGroupTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')

    def testOnlySeeOwnStageGroups(self):
        other_user = self.user_login.become_normal_user()
        other_stage_group = JobFileStageGroup.objects.create(user=other_user)
        other_job = Job.objects.create(workflow_version=self.workflow_version,
                                       job_order='{}',
                                       user=other_user,
                                       stage_group=other_stage_group,
                                       share_group=self.share_group,
                                       job_settings=self.job_settings,
                                       job_flavor=self.job_flavor,
                                       )
        this_user = self.user_login.become_other_normal_user()
        this_stage_group = JobFileStageGroup.objects.create(user=this_user)
        this_job = Job.objects.create(workflow_version=self.workflow_version,
                                      job_order='{}',
                                      user=this_user,
                                      stage_group=this_stage_group,
                                      share_group=self.share_group,
                                      job_settings=self.job_settings,
                                      job_flavor=self.job_flavor,
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
                                                               url=cwl_url,
                                                               fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')

    def testNormalUserReadOnly(self):
        other_user = self.user_login.become_normal_user()
        other_job = Job.objects.create(workflow_version=self.workflow_version,
                                       job_order='{}',
                                       user=other_user,
                                       share_group=self.share_group,
                                       job_settings=self.job_settings,
                                       job_flavor=self.job_flavor,
                                       )
        JobError.objects.create(job=other_job, content='Out of memory.', job_step=Job.JOB_STEP_RUNNING)
        # Normal user can't write
        url = reverse('joberror-list')
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        my_user = self.user_login.become_other_normal_user()
        my_job = Job.objects.create(workflow_version=self.workflow_version,
                                    job_order='{}',
                                    user=my_user,
                                    share_group=self.share_group,
                                    job_settings=self.job_settings,
                                    job_flavor=self.job_flavor,
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
                                    job_order='{}',
                                    user=my_user,
                                    share_group=self.share_group,
                                    job_settings=self.job_settings,
                                    job_flavor=self.job_flavor,
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
                                                               url=cwl_url,
                                                               fields=[])
        self.other_user = self.user_login.become_other_normal_user()
        self.my_user = self.user_login.become_normal_user()
        self.stage_group = JobFileStageGroup.objects.create(user=self.my_user)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')
        self.my_job = Job.objects.create(workflow_version=self.workflow_version,
                                         job_order='{}',
                                         user=self.my_user,
                                         stage_group=self.stage_group,
                                         share_group=self.share_group,
                                         job_settings=self.job_settings,
                                         job_flavor=self.job_flavor,
                                         )
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
            'sequence_group': 1,
            'sequence': 1,
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
            'sequence_group': 1,
            'sequence': 1,
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
            'size': 8 * 1024 * 1024 * 1024,
            'sequence_group': 1,
            'sequence': 1,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class URLJobInputFileTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.my_user = self.user_login.become_normal_user()
        self.stage_group = JobFileStageGroup.objects.create(user=self.my_user)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')
        self.my_job = Job.objects.create(workflow_version=self.workflow_version,
                                         job_order='{}',
                                         user=self.my_user,
                                         stage_group=self.stage_group,
                                         share_group=self.share_group,
                                         job_settings=self.job_settings,
                                         job_flavor=self.job_flavor,
                                         )

    def testPostAndRead(self):
        url = reverse('urljobinputfile-list')
        response = self.client.post(url, format='json', data={
            'stage_group': self.stage_group.id,
            'url': 'http://stuff.com/data.txt',
            'destination_path': 'data.txt',
            'sequence_group': 1,
            'sequence': 1,
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
            'size': 8 * 1024 * 1024 * 1024,
            'sequence_group': 1,
            'sequence': 1,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class JobDDSOutputProjectTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.other_user = self.user_login.become_other_normal_user()
        self.my_user = self.user_login.become_normal_user()
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')
        self.my_job = Job.objects.create(workflow_version=self.workflow_version,
                                         job_order='{}',
                                         user=self.my_user,
                                         share_group=self.share_group,
                                         job_settings=self.job_settings,
                                         job_flavor=self.job_flavor,
                                         )
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret', api_root='https://someserver.com/api')
        self.cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=self.my_user, token='secret2',
                                                     dds_id='1')
        self.others_cred = DDSUserCredential.objects.create(endpoint=self.endpoint, user=self.other_user,
                                                            token='secret3', dds_id='2')

    def test_list_dirs(self):
        JobDDSOutputProject.objects.create(job=self.my_job, project_id='1',
                                           dds_user_credentials=self.cred)
        url = reverse('jobddsoutputproject-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        job_output_project = response.data[0]
        self.assertEqual(self.my_job.id, job_output_project['job'])
        self.assertEqual('1', job_output_project['project_id'])
        self.assertEqual(self.cred.id, job_output_project['dds_user_credentials'])

    def test_create(self):
        url = reverse('jobddsoutputproject-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'project_id': '123',
            'dds_user_credentials': self.cred.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_output_project = JobDDSOutputProject.objects.first()
        self.assertEqual(self.my_job, job_output_project.job)
        self.assertEqual('123', job_output_project.project_id)
        self.assertEqual(self.cred, job_output_project.dds_user_credentials)

    def test_user_cant_change_remote_file_id(self):
        url = reverse('jobddsoutputproject-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'project_id': '123',
            'dds_user_credentials': self.cred.id,
            'readme_file_id': '123',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_output_project = JobDDSOutputProject.objects.first()
        self.assertEqual('', job_output_project.readme_file_id)

    def test_can_use_others_creds(self):
        url = reverse('jobddsoutputproject-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'project_id': '123',
            'dds_user_credentials': self.others_cred.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_dirs_admin(self):
        # Admin can list other users job-output-directories
        JobDDSOutputProject.objects.create(job=self.my_job, project_id='1',
                                           dds_user_credentials=self.cred)
        self.user_login.become_admin_user()
        url = reverse('admin_jobddsoutputproject-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        job_output_project = response.data[0]
        self.assertEqual(self.my_job.id, job_output_project['job'])
        self.assertEqual('1', job_output_project['project_id'])
        self.assertEqual(self.cred.id, job_output_project['dds_user_credentials'])

    def test_create_admin(self):
        # Admin can create other users job-output-directories
        self.user_login.become_admin_user()
        url = reverse('admin_jobddsoutputproject-list')
        response = self.client.post(url, format='json', data={
            'job': self.my_job.id,
            'project_id': '123',
            'dds_user_credentials': self.cred.id,
            'readme_file_id': '456',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_output_project = JobDDSOutputProject.objects.first()
        self.assertEqual(self.my_job, job_output_project.job)
        self.assertEqual('123', job_output_project.project_id)
        self.assertEqual(self.cred, job_output_project.dds_user_credentials)
        self.assertEqual('456', job_output_project.readme_file_id)

    def test_readme_url_endpoint_get(self):
        job_output_project = JobDDSOutputProject.objects.create(job=self.my_job, project_id='1',
                                                            dds_user_credentials=self.cred)
        url = '{}{}/readme-url/'.format(reverse('jobddsoutputproject-list'), job_output_project.id)
        response = self.client.get(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('data.util.RemoteStore')
    def test_readme_url_endpoint_post(self, mock_remote_store):
        mock_remote_store.return_value.data_service.get_file_url.return_value.json.return_value = {
            'http_verb': 'GET',
            'url': 'someurl',
            'host': 'somehost',
            'http_headers': '',
        }
        job_output_project = JobDDSOutputProject.objects.create(job=self.my_job, project_id='1',
                                                            dds_user_credentials=self.cred)
        url = '{}{}/readme-url/'.format(reverse('jobddsoutputproject-list'), job_output_project.id)
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('http_verb'), 'GET')
        self.assertEqual(response.data.get('url'), 'someurl')
        self.assertEqual(response.data.get('host'), 'somehost')
        self.assertEqual(response.data.get('http_headers'), '')


class JobQuestionnaireTestCase(APITestCase):
    def setUp(self):
        """
        Create two questionnaires since this should be a read only endpoint.
        """
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq', tag='rnaseq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.system_job_order_json1 = json.dumps({'system_input': 1})
        self.system_job_order_json2 = json.dumps({'system_input': 2})
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.workflow_version2 = WorkflowVersion.objects.create(workflow=workflow,
                                                                version="2",
                                                                url=cwl_url,
                                                                fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        questionnaire_type1 = JobQuestionnaireType.objects.create(tag='human')
        questionnaire_type2 = JobQuestionnaireType.objects.create(tag='ant')
        self.questionnaire1 = JobQuestionnaire.objects.create(name='Workflow1',
                                                              description='A really large workflow',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json1,
                                                              share_group=self.share_group,
                                                              job_settings=self.job_settings,
                                                              job_flavor=self.job_flavor,
                                                              type=questionnaire_type1
                                                              )
        self.questionnaire2 = JobQuestionnaire.objects.create(name='Workflow2',
                                                              description='A rather small workflow',
                                                              workflow_version=self.workflow_version2,
                                                              system_job_order_json=self.system_job_order_json2,
                                                              share_group=self.share_group,
                                                              job_settings=self.job_settings,
                                                              job_flavor=self.job_flavor,
                                                              type=questionnaire_type2
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
        self.assertEqual(self.job_settings.id, response.data['vm_settings'])

        url = '{}{}/'.format(reverse('jobquestionnaire-list'), self.questionnaire2.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('Workflow2', response.data['name'])
        self.assertEqual('A rather small workflow', response.data['description'])
        self.assertEqual(self.workflow_version2.id, response.data['workflow_version'])
        self.assertEqual(self.system_job_order_json2, response.data['system_job_order_json'])
        self.assertEqual(self.job_settings.id, response.data['vm_settings'])

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

    def test_filter_by_tag(self):
        self.user_login.become_normal_user()
        url = reverse('jobquestionnaire-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        url = reverse('jobquestionnaire-list') + "?tag={}".format(self.questionnaire1.make_tag())
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], self.questionnaire1.name)

    def test_filter_by_workflow_version(self):
        self.user_login.become_normal_user()
        url = reverse('jobquestionnaire-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        url = reverse('jobquestionnaire-list') + "?workflow_version={}".format(self.questionnaire2.workflow_version_id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], self.questionnaire2.name)


class JobAnswerSetTests(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq', tag='rna-seq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        add_job_settings(self)
        self.job_flavor = JobFlavor.objects.create(name='flavor')
        self.system_job_order_json1 = json.dumps({'system_input': 1})
        self.system_job_order_json2 = json.dumps({'system_input': 2})
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.questionnaire_type = JobQuestionnaireType.objects.create(tag='human')
        self.questionnaire1 = JobQuestionnaire.objects.create(description='Workflow1',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json1,
                                                              share_group=self.share_group,
                                                              job_settings=self.job_settings,
                                                              job_flavor=self.job_flavor,
                                                              type=self.questionnaire_type,
                                                              )
        self.questionnaire2 = JobQuestionnaire.objects.create(description='Workflow1',
                                                              workflow_version=self.workflow_version,
                                                              system_job_order_json=self.system_job_order_json2,
                                                              share_group=self.share_group,
                                                              job_settings=self.job_settings,
                                                              job_flavor=self.job_flavor,
                                                              type=self.questionnaire_type,
                                                              )
        self.other_user = self.user_login.become_other_normal_user()
        self.user = self.user_login.become_normal_user()
        self.stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret',
                                                   api_root='https://someserver.com/api')
        self.user_job_order_json1 = json.dumps({'input1': 'value1'})
        self.user_job_order_json2 = json.dumps({'input1': 'value1', 'input2': [1, 2, 3]})
        # creating a job defaults to the first dds_user_credential
        self.dds_user_credential = DDSUserCredential.objects.create(
            endpoint=self.endpoint,
            user=self.user,
            token='dds-user-credential-token',
            dds_id='dds-user-id'
        )

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
        add_job_settings(self, project_name='project2', cloud_name='cloud2', settings_name='settings2')
        job_flavor = JobFlavor.objects.create(name='flavor2')
        questionnaire = JobQuestionnaire.objects.create(description='Workflow1',
                                                        workflow_version=self.workflow_version,
                                                        system_job_order_json=self.system_job_order_json1,
                                                        share_group=self.share_group,
                                                        job_settings=self.job_settings,
                                                        job_flavor=job_flavor,
                                                        type=self.questionnaire_type,
                                                        )
        return questionnaire

    @override_settings(REQUIRE_JOB_TOKENS=True)
    def test_create_job_require_job_token_true(self):
        questionnaire = self.setup_minimal_questionnaire()
        url = reverse('jobanswerset-list')
        response = self.client.post(url, format='json', data={
            'questionnaire': questionnaire.id,
            'job_name': 'Test job',
            'user_job_order_json': self.user_job_order_json1,
            'stage_group': self.stage_group.id,
            'vm_settings': self.job_settings.id,
            'fund_code': '123-5'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_answer_set_id = response.data['id']
        url = reverse('jobanswerset-list') + str(job_answer_set_id) + "/create-job/"
        response = self.client.post(url, format='json', data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(Job.JOB_STATE_NEW, response.data['state'])

    def test_create_job_with_items(self):
        questionnaire = self.setup_minimal_questionnaire()
        url = reverse('jobanswerset-list')
        response = self.client.post(url, format='json', data={
            'questionnaire': questionnaire.id,
            'job_name': 'Test job with items',
            'user_job_order_json': self.user_job_order_json1,
            'stage_group': self.stage_group.id,
            'vm_settings': self.job_settings.id,
            'fund_code': '123-5'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_answer_set_id = response.data['id']
        url = reverse('jobanswerset-list') + str(job_answer_set_id) + "/create-job/"
        response = self.client.post(url, format='json', data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual('Test job with items', response.data['name'])
        self.assertEqual(self.job_settings.id, response.data['vm_settings'])
        self.assertEqual('123-5', response.data['fund_code'])
        expected_job_order = json.loads(self.system_job_order_json1).copy()
        expected_job_order.update(json.loads(self.user_job_order_json1))
        self.assertEqual(json.dumps(expected_job_order), response.data['job_order'])
        self.assertEqual(1, len(Job.objects.all()))
        self.assertEqual(1, len(JobDDSOutputProject.objects.all()))

    @override_settings(REQUIRE_JOB_TOKENS=False)
    def test_create_job_require_job_token_false(self):
        questionnaire = self.setup_minimal_questionnaire()
        url = reverse('jobanswerset-list')
        response = self.client.post(url, format='json', data={
            'questionnaire': questionnaire.id,
            'job_name': 'Test job with items',
            'user_job_order_json': self.user_job_order_json1,
            'stage_group': self.stage_group.id,
            'vm_settings': self.job_settings.id,
            'fund_code': '123-5'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_answer_set_id = response.data['id']
        url = reverse('jobanswerset-list') + str(job_answer_set_id) + "/create-job/"
        response = self.client.post(url, format='json', data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(Job.JOB_STATE_AUTHORIZED, response.data['state'])

    @patch('data.jobfactory.JobDDSOutputProject')
    def test_create_job_with_exception_rolls_back(self, MockJobDDSOutputProject):
        MockJobDDSOutputProject.objects.create.side_effect = ValueError("oops")
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
        share_group1.email = 'data1@example.com'
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        url = reverse('admin_sharegroup-list') + "{}/".format(share_group1.id)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group = response.data
        self.assertEqual('Data validation team 1', group['name'])
        self.assertEqual('data1@example.com', group['email'])
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
        share_group1 = ShareGroup.objects.create(name='Data validation team 1', email='data1@example.com')
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        share_group2 = ShareGroup.objects.create(name='Data validation team 2', email='data2@example.com')
        share_group2.users = [dds_user1, dds_user3]
        share_group2.save()

        url = reverse('sharegroup-list')
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        group = response.data[0]
        self.assertEqual('Data validation team 1', group['name'])
        self.assertEqual('data1@example.com', group['email'])
        self.assertEqual(None, group.get('users'))  # Regular users cannot see users in groups
        group = response.data[1]
        self.assertEqual('Data validation team 2', group['name'])
        self.assertEqual('data2@example.com', group['email'])
        self.assertEqual(None, group.get('users'))  # Regular users cannot see users in groups

    def test_user_read_single_group(self):
        # Test that we can read a single group (so we can share results with the group members)
        dds_user1 = DDSUser.objects.create(name='Joe', dds_id='123')
        dds_user2 = DDSUser.objects.create(name='Jim', dds_id='456')
        share_group1 = ShareGroup.objects.create(name='Data validation team 1', email='data@example.com')
        share_group1.users = [dds_user1, dds_user2]
        share_group1.save()
        url = reverse('sharegroup-list') + "{}/".format(share_group1.id)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group = response.data
        self.assertEqual('Data validation team 1', group['name'])
        self.assertEqual('data@example.com', group['email'])
        self.assertEqual(None, group.get('users'))  # Regular users cannot see users in groups


class WorkflowMethodsDocumentTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow1 = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow1, version="1", url=cwl_url,fields=[])
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


class EmailMessageTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_admin_only_allow_admin_users(self):
        url = reverse('admin_emailmessage-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_list(self):
        EmailMessage.objects.create(
            body='body1',
            subject='subject1',
            sender_email='sender1@example.com',
            to_email='recipient1@university.edu',
        )
        EmailMessage.objects.create(
            body='body2',
            subject='subject2',
            sender_email='sender2@example.com',
            to_email='recipient2@university.edu',
        )
        EmailMessage.objects.create(
            body='body3',
            subject='subject3',
            sender_email='sender3@example.com',
            to_email='recipient3@university.edu',
        )

        url = reverse('admin_emailmessage-list')
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(3, len(response.data))
        messages = response.data

        self.assertEqual('body1', messages[0]['body'])
        self.assertEqual('body2', messages[1]['body'])
        self.assertEqual('body3', messages[2]['body'])

    def test_admin_read_single_message(self):
        message = EmailMessage.objects.create(
            body='body1',
            subject='subject1',
            sender_email='sender1@example.com',
            to_email='recipient1@university.edu',
        )

        url = reverse('admin_emailmessage-detail', args=[message.id])
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('body1', response.data['body'])
        self.assertEqual('subject1', response.data['subject'])
        self.assertEqual('sender1@example.com', response.data['sender_email'])
        self.assertEqual('recipient1@university.edu', response.data['to_email'])
        self.assertEqual('N', response.data['state'])

    def test_admin_create_message(self):
        message_dict = {
            'body': 'Email message body',
            'subject': 'Subject',
            'sender_email': 'fred@school.edu',
            'to_email': 'wilma@company.com'
        }
        url = reverse('admin_emailmessage-list')
        self.user_login.become_admin_user()
        response = self.client.post(url, format='json', data=message_dict)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = EmailMessage.objects.first()
        self.assertEqual('Subject', created.subject)
        self.assertEqual('Email message body', created.body)
        self.assertEqual('fred@school.edu', created.sender_email)
        self.assertEqual('wilma@company.com', created.to_email)

    @patch('data.mailer.DjangoEmailMessage')
    def test_admin_send_message(self, MockSender):
        message = EmailMessage.objects.create(
            body='body1',
            subject='subject1',
            sender_email='sender1@example.com',
            to_email='recipient1@university.edu',
        )
        url = reverse('admin_emailmessage-detail', args=[message.id])  + 'send/'
        self.user_login.become_admin_user()
        response = self.client.post(url, format='json', data={})
        self.assertTrue(MockSender.called)
        self.assertTrue(MockSender.return_value.send.called)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual('S', response.data['state'])

    @patch('data.mailer.DjangoEmailMessage')
    def test_admin_send_message_with_error(self, MockSender):
        MockSender.return_value.send.side_effect = Exception()
        message = EmailMessage.objects.create(
            body='body1',
            subject='subject1',
            sender_email='sender1@example.com',
            to_email='recipient1@university.edu',
        )
        url = reverse('admin_emailmessage-detail', args=[message.id])  + 'send/'
        self.user_login.become_admin_user()
        response = self.client.post(url, format='json', data={})
        self.assertTrue(MockSender.called)
        self.assertTrue(MockSender.return_value.send.called)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        message = EmailMessage.objects.get(id=message.id)
        self.assertEqual(message.state, 'E')


class EmailTemplateTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_admin_only_allow_admin_users(self):
        url = reverse('admin_emailtemplate-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.user_login.become_normal_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_list(self):
        EmailTemplate.objects.create(
            name='template1',
            body_template='body_template1',
            subject_template='subject_template1',
        )
        EmailTemplate.objects.create(
            name='template2',
            body_template='body_template2',
            subject_template='subject_template2',
        )
        EmailTemplate.objects.create(
            name='template3',
            body_template='body_template3',
            subject_template='subject_template3',
        )

        url = reverse('admin_emailtemplate-list')
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(3, len(response.data))
        messages = response.data

        self.assertEqual('body_template1', messages[0]['body_template'])
        self.assertEqual('body_template2', messages[1]['body_template'])
        self.assertEqual('body_template3', messages[2]['body_template'])

    def test_admin_read_single_template(self):
        template = EmailTemplate.objects.create(
            name='template1',
            body_template='body1',
            subject_template='subject1',
        )

        url = reverse('admin_emailtemplate-detail', args=[template.id])
        self.user_login.become_admin_user()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('template1', response.data['name'])
        self.assertEqual('body1', response.data['body_template'])
        self.assertEqual('subject1', response.data['subject_template'])

    def test_admin_create_template(self):
        template_dict = {
            'name': 'error-template',
            'body_template': 'The following error occurred {{ error }}',
            'subject_template': 'Error for job {{ job.name }}',
        }
        url = reverse('admin_emailtemplate-list')
        self.user_login.become_admin_user()
        response = self.client.post(url, format='json', data=template_dict)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = EmailTemplate.objects.first()
        self.assertEqual('error-template', created.name)


class UserTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_requires_login(self):
        self.user_login.become_unauthorized()
        url = reverse('user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_list(self):
        with self.assertRaises(NoReverseMatch):
            reverse('user-list')

    def test_get_current_user(self):
        self.user_login.become_normal_user()
        url = reverse('user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user')

        self.user_login.become_other_normal_user()
        url = reverse('user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user2')

    def test_cannot_change(self):
        self.user_login.become_normal_user()
        url = reverse('user-current-user')
        response = self.client.put(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response = self.client.delete(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_get_by_id(self):
        self.user_login.become_normal_user()
        url = reverse('user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user')
        user_id = response.data['id']
        self.assertIsNotNone(django_user.objects.get(id=user_id))
        detail_url = '{}/{}'.format(url, user_id)
        response = self.client.get(detail_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class JobActivitiesTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="1",
                                                               url=cwl_url,
                                                               fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.job_flavor = JobFlavor.objects.create(name='flavor1')
        add_job_settings(self)

    @staticmethod
    def get_job_details(response):
        return [(item['job'], item['state'], item['step']) for item in response.data]

    def test_user_only_sees_their_data(self):
        url = reverse('jobactivity-list')
        normal_user = self.user_login.become_normal_user()
        job1 = Job.objects.create(name='my job',
                                  workflow_version=self.workflow_version,
                                  job_order={},
                                  user=normal_user,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  )
        job1.state = Job.JOB_STATE_RUNNING
        job1.step = Job.JOB_STEP_CREATE_VM
        job1.save()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_job_details(response), [
            (job1.id, Job.JOB_STATE_NEW, ''),
            (job1.id, Job.JOB_STATE_RUNNING, Job.JOB_STEP_CREATE_VM),
        ])

        # switch to another user and we shouldn't see job1 activities
        other_user = self.user_login.become_other_normal_user()
        job2 = Job.objects.create(name='other job',
                                  workflow_version=self.workflow_version,
                                  job_order={},
                                  user=other_user,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  )
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_job_details(response), [
            (job2.id, Job.JOB_STATE_NEW, ''),
        ])

    def test_users_can_filter_by_job(self):
        normal_user = self.user_login.become_normal_user()
        job1 = Job.objects.create(name='my job',
                                  workflow_version=self.workflow_version,
                                  job_order={},
                                  user=normal_user,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  )
        job2 = Job.objects.create(name='my job2',
                                  workflow_version=self.workflow_version,
                                  job_order={},
                                  user=normal_user,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  state=Job.JOB_STATE_RUNNING
                                  )
        url = reverse('jobactivity-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_job_details(response), [
            (job1.id, Job.JOB_STATE_NEW, ''),
            (job2.id, Job.JOB_STATE_RUNNING, ''),
        ])
        job2.step = Job.JOB_STEP_RUNNING
        job2.save()

        response = self.client.get('{}?job={}'.format(url, job2.id), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_job_details(response), [
            (job2.id, Job.JOB_STATE_RUNNING, ''),
            (job2.id, Job.JOB_STATE_RUNNING, Job.JOB_STEP_RUNNING),
        ])


class AdminImportWorkflowQuestionnaireTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        # Data needs to deserialize
        self.data = {"cwl_url": "https://example.org/exome-seq.cwl",
            "workflow_version_number": 12,
            "name": "Test Questionnaire Name",
            "description" : "Test Questionnaire Description",
            "workflow_tag": "my-tag",
            "type_tag": "human",
            "methods_template_url": "https://example.org/exome-seq.md.j2",
            "system_json": {
                "threads": 4,
                "files": [
                    {
                        "class": "File",
                        "path":"/nfs/data/genome.fa"
                    }
                ]
            },
            "vm_settings_name": "test-settings",
            "vm_flavor_name": "test-flavor",
            "share_group_name": "test-share-group",
            "volume_size_base": 100,
            "volume_size_factor": 10
        }

    def test_denies_get(self):
        self.user_login.become_admin_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_denies_put(self):
        self.user_login.become_admin_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.put(url, self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_denies_delete(self):
        self.user_login.become_admin_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('data.api.WorkflowQuestionnaireImporter')
    def test_loads_questionnaire(self, mock_importer):
        mock_run = Mock()
        mock_importer.return_value.run = mock_run
        mock_importer.return_value.created_jobquestionnaire = True
        self.user_login.become_admin_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.post(url, self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that the Questionnaire importer was called with our POSTed data
        args, kwargs = mock_importer.call_args
        self.assertEqual(args, (self.data,))
        self.assertEqual(kwargs, {})
        self.assertTrue(mock_run.called)

    def test_unauthenticated_user_cannot_post(self):
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.put(url, self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_normal_user_cannot_post(self):
        self.user_login.become_normal_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.put(url, self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fails_bad_system_json(self):
        # DictField on the serializer checks this
        self.user_login.become_admin_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        self.data['system_json'] = 'not-json]'
        response = self.client.post(url, self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('data.api.WorkflowQuestionnaireImporter')
    def test_returns_200_when_questionnaire_exists(self, mock_importer):
        mock_run = Mock()
        mock_importer.return_value.run = mock_run
        mock_importer.return_value.created_jobquestionnaire = False
        self.user_login.become_admin_user()
        url = reverse('admin_importworkflowquestionnaire-list')
        response = self.client.post(url, self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TokenTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def testFailsUnauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('token-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testListOnlyShowsCurrentUsersTokens(self):
        other_user = self.user_login.become_other_normal_user()
        Token.objects.create(user=other_user)
        normal_user = self.user_login.become_normal_user()
        current_user_token = Token.objects.create(user=normal_user)
        self.assertEqual(Token.objects.count(), 2)

        url = reverse('token-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], current_user_token.key)
        created_str = current_user_token.created.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.assertEqual(response.data[0]['created'], created_str)

    def testCreate(self):
        normal_user = self.user_login.become_normal_user()
        url = reverse('token-list')
        self.assertEqual(Token.objects.filter(user=normal_user).count(), 0)

        # when a user has no tokens they can create a token
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Token.objects.filter(user=normal_user).count(), 1)
        token = Token.objects.get(user=normal_user)
        self.assertEqual(response.data['id'], token.key)
        created_str = token.created.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.assertEqual(response.data['created'], created_str)

        # when a user has a tokens they cannot create a token
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        token.delete()
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testGet(self):
        normal_user = self.user_login.become_normal_user()
        token = Token.objects.create(user=normal_user)
        url = reverse('token-list') + token.key + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], token.key)

    def testPutForbidden(self):
        normal_user = self.user_login.become_normal_user()
        url = reverse('token-list')
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testDelete(self):
        normal_user = self.user_login.become_normal_user()
        token = Token.objects.create(user=normal_user)
        url = reverse('token-list') + token.key + '/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
