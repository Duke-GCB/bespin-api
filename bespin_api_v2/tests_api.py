import json
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from data.tests_api import UserLogin
from data.models import Workflow, WorkflowVersion, WorkflowConfiguration, JobStrategy, ShareGroup, JobFlavor, \
    JobSettings, CloudSettingsOpenStack, VMProject, JobFileStageGroup, DDSUserCredential, DDSEndpoint, Job, \
    JobRuntimeK8s, LandoConnection, JobRuntimeStepK8s, EmailMessage, EmailTemplate, WorkflowVersionToolDetails
from data.tests_models import create_vm_job_settings
from bespin_api_v2.jobtemplate import STRING_VALUE_PLACEHOLDER, INT_VALUE_PLACEHOLDER, \
    REQUIRED_ERROR_MESSAGE, PLACEHOLDER_ERROR_MESSAGE
from mock import patch, Mock


class AdminCreateListRetrieveMixin(object):
    """
    Many of our Admin models are CreateListRetrieveModelViewSet subclasses, therefore
    most of the API tests follow the same pattern. This base class provides test for the standard behaviors
    """

    # Override these variables and methods in implementation
    BASE_NAME = None # Name of the base_view from urls, e.g. 'v2-workflowversiontooldetails'
    MODEL_CLS = None # Name of the model class

    def create_model_object(self):
        raise NotImplemented('Override create_model_object to use this base class')

    def build_post_data(self):
        raise NotImplemented('Override build_post_data to use this base class')

    def check_single_response(self, model_object, response_data):
        raise NotImplemented('Override check_single_response to use this base class')

    # May override
    def check_list_response(self, model_object, response_data):
        self.assertEqual(len(response_data), 1, 'Should have one item as one item was created')
        self.check_single_response(model_object, response_data[0])

    # Do not override
    def list_url(self):
        return reverse('{}-list'.format(self.BASE_NAME))

    def object_url(self, pk):
        return '{}{}/'.format(self.list_url(), pk)

    def get_model_object(self, pk):
        return self.MODEL_CLS.objects.get(pk=pk)

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = self.list_url()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_not_admin_user(self):
        self.user_login.become_normal_user()
        url = self.list_url()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_with_admin_user(self):
        model_object = self.create_model_object()
        self.user_login.become_admin_user()
        url = self.list_url()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_list_response(model_object, response.data)

    def test_retrieve_with_admin_user(self):
        model_object = self.create_model_object()
        self.user_login.become_admin_user()
        url = self.object_url(model_object.id)
        response = self.client.get(url ,format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_single_response(model_object, response.data)

    def test_create_with_admin_user(self):
        self.user_login.become_admin_user()
        url = self.list_url()
        response = self.client.post(url, format='json', data=self.build_post_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        model_object = self.get_model_object(response.data['id'])
        self.check_single_response(model_object, response.data)

    def test_put_fails_with_admin_user(self):
        self.user_login.become_admin_user()
        url = self.object_url('placeholder-id')
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_admin_user(self):
        self.user_login.become_admin_user()
        url = self.object_url('placeholder-id')
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AdminWorkflowViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):

    BASE_NAME = 'v2-admin_workflow'
    MODEL_CLS = Workflow

    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/workflows/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/workflows/3/')

    def create_model_object(self):
        model_object = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['tag'], 'exomeseq')

    def build_post_data(self):
        return {
            'name': 'Exome Seq',
            'tag': 'exomeseq',
        }


class AdminWorkflowVersionViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):

    BASE_NAME = 'v2-admin_workflowversion'
    MODEL_CLS = WorkflowVersion

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.version_change_log = 'https://github.com/bespin-workflows/exomeseq-gatk3/blob/release-4.1/CHANGELOG.md'

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/workflow-versions/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/workflow-versions/3/')

    def create_model_object(self):
        model_object = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version='1.0.1',
            version_info_url=self.version_change_log,
            url='https://someurl.com',
            fields=[{"name":"threads", "class": "int"}],
        )
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['workflow'], self.workflow.id)
        self.assertEqual(response_data['description'], 'v1 exomeseq')
        self.assertEqual(response_data['version'], '1.0.1')
        self.assertEqual(response_data['url'], 'https://someurl.com')
        self.assertEqual(response_data['fields'], [{"name": "threads", "class": "int"}])

    def build_post_data(self):
        return {
            'workflow': self.workflow.id,
            'description': 'v1 exomeseq',
            'version': '1.0.1',
            'url': 'https://someurl.com',
            'fields': [{"name": "threads", "class": "int"}],
        }

    # Additional tests
    def test_create_with_version_change_log(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list')
        response = self.client.post(url, format='json', data={
            'workflow': self.workflow.id,
            'description': 'v1 exomseq',
            'version': '2.0.1',
            'url': 'https://someurl.com',
            'version_info_url': 'https://someurl.com/changelog',
            'fields': [{"name": "threads", "class": "int"}],

        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['description'], 'v1 exomseq')
        self.assertEqual(response.data['enable_ui'], False)
        workflow_versions = WorkflowVersion.objects.all()
        self.assertEqual(len(workflow_versions), 1)
        self.assertEqual(workflow_versions[0].version, '2.0.1')
        self.assertEqual(workflow_versions[0].version_info_url, 'https://someurl.com/changelog')
        self.assertEqual(workflow_versions[0].fields, [{"name": "threads", "class": "int"}])

    def test_sorted_by_workflow_and_version(self):
        wf1 = Workflow.objects.create(name='workflow1', tag='one')
        wfv_1 = WorkflowVersion.objects.create(workflow=wf1, version="1", url='', fields=[])
        wfv_2_2_2_dev = WorkflowVersion.objects.create(workflow=wf1, version="2.2.2-dev", url='', fields=[])
        wfv_1_3_1 = WorkflowVersion.objects.create(workflow=wf1, version="1.3.1", url='', fields=[])
        wf2 = Workflow.objects.create(name='workflow2', tag='two')
        wfv_5 = WorkflowVersion.objects.create(workflow=wf2, version="5", url='', fields=[])

        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        workflow_versions_ary = [(item['workflow'], item['version']) for item in response.data]
        self.assertEqual(workflow_versions_ary, [
            (wf1.id, '1'),
            (wf1.id, '1.3.1'),
            (wf1.id, '2.2.2-dev'),
            (wf2.id, '5'),
        ])

    def test_includes_tool_details(self):
        workflow_version = self.create_model_object()
        details = WorkflowVersionToolDetails.objects.create(
            workflow_version=workflow_version,
            details=[{'k':'v'}]
        )
        self.user_login.become_admin_user()
        url = self.object_url(workflow_version.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tool_details'], details.pk)


class AdminWorkflowConfigurationViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):

    BASE_NAME = 'v2-admin_workflowconfiguration'
    MODEL_CLS = WorkflowConfiguration

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version='1',
            url='',
            fields=[{"name": "threads", "class": "int"}]
        )
        job_flavor = JobFlavor.objects.create(name='large')
        vm_project = VMProject.objects.create()
        lando_connection = LandoConnection.objects.create(
            cluster_type=LandoConnection.K8S_TYPE,
            host='somehost',
            username='user1',
            password='secret',
            queue_name='lando'
        )
        job_settings = JobSettings.objects.create(lando_connection=lando_connection, job_runtime_k8s=JobRuntimeK8s.objects.create())

        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=job_flavor, job_settings=job_settings)
        self.share_group = ShareGroup.objects.create()

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/workflow-configurations/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/workflow-configurations/3/')

    def create_model_object(self):
        model_object = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A":"B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['tag'], 'b37xGen')
        self.assertEqual(response_data['workflow'], self.workflow.id)
        self.assertEqual(response_data['system_job_order'], {"A": "B"})
        self.assertEqual(response_data['default_job_strategy'], self.job_strategy.id)
        self.assertEqual(response_data['share_group'], self.share_group.id)

    def build_post_data(self):
        return {
            'workflow': self.workflow.id,
            'tag': 'b37xGen',
            'system_job_order': {"A": "B"},
            'default_job_strategy': self.job_strategy.id,
            'share_group': self.share_group.id,
        }


class AdminWorkflowVersionToolDetailsViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):

    BASE_NAME = 'v2-workflowversiontooldetails'
    MODEL_CLS = WorkflowVersionToolDetails

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Test Workflow', tag='test')
        self.workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='Test vABC',
            version='vABC',
            url='https://example.org/test.zip',
            fields=[{'name': 'size', 'type': 'int'},]
        )
        self.details = [{'k1': 'v1'}, {'k2': 'v2'}]

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/workflow-version-tool-details/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/workflow-version-tool-details/3/')

    def create_model_object(self):
        model_object = WorkflowVersionToolDetails.objects.create(
            workflow_version=self.workflow_version,
            details=self.details
        )
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['workflow_version'], self.workflow_version.id)
        self.assertEqual(response_data['details'], self.details)

    def build_post_data(self):
        return {
            'workflow_version': self.workflow_version.id,
            'details': self.details
        }


class JobStrategyViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.job_flavor = JobFlavor.objects.create(name='large')
        self.job_settings = create_vm_job_settings()

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-jobstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_normal_user(self):
        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=self.job_flavor,
                                                     job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.job_strategy.id)
        self.assertEqual(response.data[0]['name'], 'default')
        self.assertEqual(response.data[0]['job_flavor']['name'], 'large')
        self.assertEqual(response.data[0]['job_settings'], self.job_settings.id)

    def test_list_filtering(self):
        JobStrategy.objects.create(name='default', job_flavor=self.job_flavor, job_settings=self.job_settings)
        JobStrategy.objects.create(name='better', job_flavor=self.job_flavor, job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['name'] for item in response.data]), set(['default', 'better']))
        url = reverse('v2-jobstrategies-list') + "?name=better"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(set([item['name'] for item in response.data]), set(['better']))

    def test_retrieve_with_normal_user(self):
        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=self.job_flavor,
                                                     job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list') + str(self.job_strategy.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.job_strategy.id)
        self.assertEqual(response.data['name'], 'default')
        self.assertEqual(response.data['job_flavor']['id'], self.job_flavor.id)
        self.assertEqual(response.data['job_settings'], self.job_settings.id)

    def test_post_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list') + '1/'
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list') + '1/'
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list') + '1/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class WorkflowConfigurationViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.workflow2 = Workflow.objects.create(name='Microbiome', tag='microbiome')
        self.workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version='1',
            url='',
            fields=[{"name":"threads", "type": "int"},{"name":"items", "type": "int"}],
        )
        self.workflow_version2 = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v2 exomeseq',
            version='2',
            url='',
            fields=[{"name":"threads", "type": "int"}],
        )
        job_flavor = JobFlavor.objects.create(name='large')
        job_settings = create_vm_job_settings()

        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=job_flavor, job_settings=job_settings)
        self.share_group = ShareGroup.objects.create()
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret',
                                                   api_root='https://someserver.com/api')

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-workflowconfigurations-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_normal_user(self):
        workflow_configuration = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A": "B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        self.user_login.become_normal_user()
        url = reverse('v2-workflowconfigurations-list')
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], workflow_configuration.id)
        self.assertEqual(response.data[0]['tag'], 'b37xGen')
        self.assertEqual(response.data[0]['workflow'], self.workflow.id)
        self.assertEqual(response.data[0]['system_job_order'], {"A": "B"})
        self.assertEqual(response.data[0]['default_job_strategy'], self.job_strategy.id)
        self.assertEqual(response.data[0]['share_group'], self.share_group.id)

    def test_list_normal_user_with_workflow_tag_filtering(self):
        workflow_configuration1 = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A": "B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        workflow_configuration2 = WorkflowConfiguration.objects.create(
            tag='b37other',
            workflow=self.workflow2,
            system_job_order={"A": "C"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        self.user_login.become_normal_user()
        url = reverse('v2-workflowconfigurations-list')
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 2)

        url = reverse('v2-workflowconfigurations-list') + "?workflow__tag=microbiome"
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['tag'], 'b37other')

    def test_list_normal_user_with_tag_filtering(self):
        workflow_configuration1 = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A": "B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        workflow_configuration2 = WorkflowConfiguration.objects.create(
            tag='b37other',
            workflow=self.workflow2,
            system_job_order={"A": "C"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        self.user_login.become_normal_user()
        url = reverse('v2-workflowconfigurations-list')
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 2)

        url = reverse('v2-workflowconfigurations-list') + "?tag=b37other"
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['tag'], 'b37other')

    def test_retrieve_normal_user(self):
        workflow_configuration = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"items": 4},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        self.user_login.become_normal_user()
        url = reverse('v2-workflowconfigurations-list') + str(workflow_configuration.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], workflow_configuration.id)
        self.assertEqual(response.data['tag'], 'b37xGen')
        self.assertEqual(response.data['workflow'], self.workflow.id)
        self.assertEqual(response.data['system_job_order'], {"items": 4})
        self.assertEqual(response.data['default_job_strategy'], self.job_strategy.id)
        self.assertEqual(response.data['share_group'], self.share_group.id)

    def test_create_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-workflowconfigurations-list')
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-workflowconfigurations-list') + '1/'
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_admin_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-workflowconfigurations-list') + '1/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-workflowconfigurations-list')
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class JobTemplatesViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.workflow2 = Workflow.objects.create(name='Microbiome', tag='microbiome')
        self.workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version='v1',
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
        )
        job_flavor = JobFlavor.objects.create(name='large')
        job_settings = create_vm_job_settings()

        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=job_flavor, job_settings=job_settings)
        self.share_group = ShareGroup.objects.create()
        self.endpoint = DDSEndpoint.objects.create(name='DukeDS', agent_key='secret',
                                                   api_root='https://someserver.com/api')
        workflow_configuration1 = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A": "B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )

    def test_init(self):
        user = self.user_login.become_normal_user()
        DDSUserCredential.objects.create(endpoint=self.endpoint, user=user, token='secret1', dds_id='1')
        stage_group = JobFileStageGroup.objects.create(user=user)
        url = reverse('v2-jobtemplate_init')
        response = self.client.post(url, format='json', data={
            'tag': 'exomeseq/v1/b37xGen'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tag'], 'exomeseq/v1/b37xGen')
        self.assertEqual(response.data['name'], STRING_VALUE_PLACEHOLDER)
        self.assertEqual(response.data['fund_code'], STRING_VALUE_PLACEHOLDER)
        self.assertEqual(response.data['job_order'],
                         {'threads': INT_VALUE_PLACEHOLDER, 'items': STRING_VALUE_PLACEHOLDER})

    def test_validate(self):
        user = self.user_login.become_normal_user()
        url = reverse('v2-jobtemplate_validate')
        response = self.client.post(url, format='json', data={
            'tag': 'exomeseq/v1/b37xGen',
            'name': 'My Job',
            'fund_code': '001',
            'job_order': {'items': 'cheese', 'threads': 1},
            'share_group': None,
            'stage_group': None,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_no_tag(self):
        user = self.user_login.become_normal_user()
        url = reverse('v2-jobtemplate_validate')
        response = self.client.post(url, format='json', data={
            'name': 'My Job',
            'fund_code': '001',
            'job_order': {'items': 'cheese', 'threads': 1},
            'share_group': None,
            'stage_group': None,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {
            'tag': [REQUIRED_ERROR_MESSAGE]
        })

    def test_validate_missing_values(self):
        user = self.user_login.become_normal_user()
        url = reverse('v2-jobtemplate_validate')
        response = self.client.post(url, format='json', data={
            'tag': 'exomeseq/v1/b37xGen',
            'job_order': {'threads': 1},
            'share_group': None,
            'stage_group': None,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {
            'name': [REQUIRED_ERROR_MESSAGE],
            'fund_code': [REQUIRED_ERROR_MESSAGE],
            'job_order.items': [REQUIRED_ERROR_MESSAGE],
        })

    def test_validate_placeholder_values(self):
        user = self.user_login.become_normal_user()
        url = reverse('v2-jobtemplate_validate')
        response = self.client.post(url, format='json', data={
            'tag': 'exomeseq/v1/b37xGen',
            'name': STRING_VALUE_PLACEHOLDER,
            'fund_code': '001',
            'job_order': {'items': STRING_VALUE_PLACEHOLDER, 'threads': INT_VALUE_PLACEHOLDER},
            'share_group': None,
            'stage_group': None,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {
            'name': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.items': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.threads': [PLACEHOLDER_ERROR_MESSAGE],
        })

    def test_create_job(self):
        user = self.user_login.become_normal_user()
        DDSUserCredential.objects.create(endpoint=self.endpoint, user=user, token='secret1', dds_id='1')
        stage_group = JobFileStageGroup.objects.create(user=user)
        url = reverse('v2-jobtemplate_createjob')
        response = self.client.post(url, format='json', data={
            'tag': 'exomeseq/v1/b37xGen',
            'name': 'My Job',
            'fund_code': '001',
            'stage_group': stage_group.id,
            'job_order': {'threads': 12, 'items': 'pie'},
            'share_group': self.share_group.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'My Job')

        jobs = Job.objects.all()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].name, 'My Job')
        self.assertEqual(jobs[0].fund_code, '001')
        self.assertEqual(json.loads(jobs[0].job_order), {'A':'B', 'threads': 12, 'items': 'pie'})

    def test_create_job_with_vm_strategy(self):
        user = self.user_login.become_normal_user()
        DDSUserCredential.objects.create(endpoint=self.endpoint, user=user, token='secret1', dds_id='1')
        stage_group = JobFileStageGroup.objects.create(user=user)
        url = reverse('v2-jobtemplate_createjob')
        response = self.client.post(url, format='json', data={
            'tag': 'exomeseq/v1/b37xGen',
            'name': 'My Job',
            'fund_code': '001',
            'stage_group': stage_group.id,
            'job_order': {'threads': 12, 'items': 'pie'},
            'share_group': self.share_group.id,
            'job_strategy': self.job_strategy.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'My Job')

        jobs = Job.objects.all()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].name, 'My Job')
        self.assertEqual(jobs[0].fund_code, '001')
        self.assertEqual(json.loads(jobs[0].job_order), {'A': 'B', 'threads': 12, 'items': 'pie'})


class ShareGroupViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.share_group = ShareGroup.objects.create(name="somegroup")

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-sharegroup-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-sharegroup-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.share_group.id)
        self.assertEqual(response.data[0]['name'], 'somegroup')

    def test_list_with_filtering(self):
        self.user_login.become_normal_user()
        url = reverse('v2-sharegroup-list')
        ShareGroup.objects.create(name="somegroup2")
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['name'] for item in response.data]), set(["somegroup", "somegroup2"]))
        url = reverse('v2-sharegroup-list') + "?name=somegroup2"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(set([item['name'] for item in response.data]), set(["somegroup2"]))

    def test_retrieve_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-sharegroup-list') + str(self.share_group.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.share_group.id)
        self.assertEqual(response.data['name'], 'somegroup')

    def test_post_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-sharegroup-list') + '1/'
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-sharegroup-list') + '1/'
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-sharegroup-list') + '1/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class WorkflowVersionsTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.workflow2 = Workflow.objects.create(name='Microbiome', tag='microbiome')
        self.workflow_version1 = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version='1.0.1',
            version_info_url='https://github.com/bespin-workflows/gatk/blob/1/CHANGELOG.md',
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
        )
        self.workflow_version2 = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v2 exomeseq',
            version='2.3.1',
            version_info_url='https://github.com/bespin-workflows/gatk/blob/2/CHANGELOG.md',
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
            enable_ui=False,
        )
        self.workflow_version3 = WorkflowVersion.objects.create(
            workflow=self.workflow2,
            description='v1 other',
            version='1.0.0-dev',
            version_info_url='https://github.com/bespin-workflows/gatk2/blob/1/CHANGELOG.md',
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
        )

    def test_list_filter_on_tag(self):
        self.user_login.become_normal_user()
        url = reverse('v2-workflowversion-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        url = reverse('v2-workflowversion-list') + '?workflow__tag=exomeseq'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['description'] for item in response.data]), set(['v1 exomeseq', 'v2 exomeseq']))

    def test_list_filter_on_version(self):
        self.user_login.become_normal_user()
        url = reverse('v2-workflowversion-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        url = reverse('v2-workflowversion-list') + '?version=2.3.1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['description'], 'v2 exomeseq')

    def test_get_details_enable_ui(self):
        self.user_login.become_normal_user()
        url = reverse('v2-workflowversion-list') + '{}/'.format(self.workflow_version1.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['enable_ui'], True)

        url = reverse('v2-workflowversion-list') + '{}/'.format(self.workflow_version2.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['enable_ui'], False)

    def test_list_version_info_url(self):
        user = self.user_login.become_normal_user()
        url = reverse('v2-workflowversion-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        version_info_urls = sorted([item['version_info_url'] for item in response.data])
        self.assertEqual(version_info_urls, [
            'https://github.com/bespin-workflows/gatk/blob/1/CHANGELOG.md',
            'https://github.com/bespin-workflows/gatk/blob/2/CHANGELOG.md',
            'https://github.com/bespin-workflows/gatk2/blob/1/CHANGELOG.md',
        ])

    def test_sorted_by_workflow_and_version(self):
        self.user_login.become_normal_user()
        url = reverse('v2-workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        workflow_versions_ary = [(item['workflow'], item['version']) for item in response.data]
        self.assertEqual(workflow_versions_ary, [
            (self.workflow.id, '1.0.1'),
            (self.workflow.id, '2.3.1'),
            (self.workflow2.id, '1.0.0-dev'),
        ])

    def test_includes_tool_details(self):
        details = WorkflowVersionToolDetails.objects.create(
            workflow_version=self.workflow_version1,
            details=[{'k':'v'}]
        )
        self.user_login.become_admin_user()
        url = reverse('v2-workflowversion-list') + '{}/'.format(self.workflow_version1.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tool_details'], details.pk)


class WorkflowVersionWorkflowStateTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.user_login.become_normal_user()
        self.active_wf = Workflow.objects.create(name='active', tag='active-tag',
                                                 state=Workflow.WORKFLOW_STATE_ACTIVE)
        self.active_version = WorkflowVersion.objects.create(workflow=self.active_wf,
                                                             version="active-version", url='', fields=[])
        self.deprecated_wf = Workflow.objects.create(name='deprecated', tag='deprecated-tag',
                                                     state=Workflow.WORKFLOW_STATE_DEPRECATED)
        self.deprecated_version = WorkflowVersion.objects.create(workflow=self.deprecated_wf,
                                                                  version="deprecated-version", url='', fields=[])

    def test_excludes_deprecated(self):
        self.assertEqual(WorkflowVersion.objects.count(), 2)
        url = reverse('v2-workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['version'], 'active-version')

    def test_includes_deprecated_when_filtering(self):
        self.assertEqual(WorkflowVersion.objects.count(), 2)
        url = reverse('v2-workflowversion-list') + "?workflow__state=D"
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['version'], 'deprecated-version')
        self.assertEqual(response.data[0]['id'], self.deprecated_version.id)

    def test_filters_on_workflow_state(self):
        self.assertEqual(WorkflowVersion.objects.count(), 2)
        url = reverse('v2-workflowversion-list') + "?workflow__state=A"
        response = self.client.get(url, format='json')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['version'], 'active-version')
        self.assertEqual(response.data[0]['id'], self.active_version.id)

    def test_can_get_deprecated_by_id(self):
        detail_url = reverse('v2-workflowversion-detail', args=[self.deprecated_version.id])
        detail_response = self.client.get(detail_url, format='json')
        self.assertEqual(detail_response.data['version'], 'deprecated-version')


class JobsTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        workflow = Workflow.objects.create(name='RnaSeq')
        cwl_url = "https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl"
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               version="v1",
                                                               url=cwl_url,
                                                               fields=[])
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.job_flavor = JobFlavor.objects.create(name='flavor1', cpus=32, memory='12Gi')
        self.vm_job_settings = create_vm_job_settings(name='vm')
        job_runtime_k8s = JobRuntimeK8s.objects.create()
        job_runtime_k8s.steps = [
            JobRuntimeStepK8s.objects.create(
                step_type=JobRuntimeStepK8s.STAGE_DATA_STEP,
                flavor=self.job_flavor,
                image_name='myimage',
                base_command=['download.py']
            )
        ]
        lando_connection = LandoConnection.objects.create(
            cluster_type=LandoConnection.K8S_TYPE,
            host='somehost', username='jpb67',
            password='secret', queue_name='lando')
        self.k8s_job_settings = JobSettings.objects.create(
            name='k8s',
            lando_connection=lando_connection,
            job_runtime_k8s=job_runtime_k8s)

    def test_jobs_list_shows_job_settings(self):
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-job-list') + '{}/'.format(job.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['job_settings'], self.vm_job_settings.id)
        self.assertNotIn('vm_settings', response.data)

    def test_admin_jobs_list_shows_vm_job_settings(self):
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['job_settings']['name'], 'vm')
        self.assertEqual(response.data['job_settings']['job_runtime_k8s'], None)
        job_runtime_openstack = response.data['job_settings']['job_runtime_openstack']
        self.assertEqual(job_runtime_openstack['image_name'], 'someimage')
        self.assertEqual(job_runtime_openstack['cwl_base_command'], ['cwltool'])
        self.assertEqual(job_runtime_openstack['cwl_post_process_command'], ['cleanup.sh'])
        self.assertEqual(job_runtime_openstack['cwl_pre_process_command'], ['prep.sh'])
        self.assertEqual(job_runtime_openstack['cloud_settings']['name'], 'cloud')
        self.assertEqual(job_runtime_openstack['cloud_settings']['vm_project']['name'], 'project1')

    def test_admin_jobs_list_shows_k8s_job_settings(self):
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=admin_user,
                                 share_group=self.share_group,
                                 job_settings=self.k8s_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['job_settings']['name'], 'k8s')
        self.assertEqual(response.data['job_settings']['job_runtime_openstack'], None)
        job_runtime_k8s_steps = response.data['job_settings']['job_runtime_k8s']['steps']
        self.assertEqual(len(job_runtime_k8s_steps), 1)
        self.assertEqual(job_runtime_k8s_steps[0]['step_type'], JobRuntimeStepK8s.STAGE_DATA_STEP)
        self.assertEqual(job_runtime_k8s_steps[0]['image_name'], 'myimage')
        self.assertEqual(job_runtime_k8s_steps[0]['base_command'],['download.py'])
        self.assertEqual(job_runtime_k8s_steps[0]['flavor']['cpus'], 32)
        self.assertEqual(job_runtime_k8s_steps[0]['flavor']['memory'], '12Gi')

    def testAdminSeeAllData(self):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='my job',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        # normal user can't see admin endpoint
        url = reverse('v2-admin_job-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        other_user = self.user_login.become_other_normal_user()
        job = Job.objects.create(name='my job2',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=other_user,
                                 share_group=self.share_group,
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        # admin user can see both via admin endpoint
        admin_user = self.user_login.become_admin_user()
        url = reverse('v2-admin_job-list')
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
        url = reverse('v2-admin_job-list')
        normal_user = self.user_login.become_normal_user()
        admin_user = self.user_login.become_admin_user()
        job = Job.objects.create(name='my job',
                                 state=Job.JOB_STATE_NEW,
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 job_settings=self.vm_job_settings,
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
                           job_settings=self.vm_job_settings,
                           job_flavor=self.job_flavor,
                           )
        Job.objects.create(name='somejob2',
                           workflow_version=self.workflow_version,
                           vm_instance_name='vm_job_2',
                           job_order={},
                           user=admin_user,
                           share_group=self.share_group,
                           job_settings=self.vm_job_settings,
                           job_flavor=self.job_flavor,
                           )
        url = reverse('v2-admin_job-list') + '?vm_instance_name=vm_job_1'
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
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)

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
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                   data={
                                        'state': Job.JOB_STATE_FINISHED,
                                        'step': Job.JOB_STEP_RUNNING,
                                   })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('bespin_api_v2.api.JobMailer')
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
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                    data={
                                        'state': Job.JOB_STATE_RUNNING,
                                        'step': Job.JOB_STEP_CREATE_VM,
                                    })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job = Job.objects.first()
        self.assertEqual(Job.JOB_STATE_RUNNING, job.state)
        self.assertEqual(Job.JOB_STEP_CREATE_VM, job.step)

    @patch('bespin_api_v2.api.JobMailer')
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
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                    data={
                                        'state': Job.JOB_STATE_RUNNING,
                                        'step': Job.JOB_STEP_CREATE_VM,
                                    })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_mail_current_state.called)

    @patch('bespin_api_v2.api.JobMailer')
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
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-admin_job-list') + '{}/'.format(job.id)
        response = self.client.put(url, format='json',
                                    data={
                                        'state': Job.JOB_STATE_RUNNING,
                                        'step': Job.JOB_STEP_RUNNING,
                                    })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(mock_mail_current_state.called)

    @patch('bespin_api_v2.api.LandoJob')
    def test_start_debug(self, mock_lando_job):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 state=Job.JOB_STATE_AUTHORIZED,
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-job-list') + '{}/start-debug/'.format(job.id)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], job.id)
        mock_lando_job.return_value.start_debug.assert_called_with()

    @patch('bespin_api_v2.api.LandoJob')
    def test_cancel_debug(self, mock_lando_job):
        normal_user = self.user_login.become_normal_user()
        job = Job.objects.create(name='somejob',
                                 workflow_version=self.workflow_version,
                                 job_order={},
                                 user=normal_user,
                                 share_group=self.share_group,
                                 state=Job.JOB_STATE_AUTHORIZED,
                                 job_settings=self.vm_job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        url = reverse('v2-job-list') + '{}/cancel-debug/'.format(job.id)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], job.id)
        mock_lando_job.return_value.cancel_debug.assert_called_with()


class EmailMessageTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_admin_only_allow_admin_users(self):
        url = reverse('v2-admin_emailmessage-list')
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

        url = reverse('v2-admin_emailmessage-list')
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

        url = reverse('v2-admin_emailmessage-detail', args=[message.id])
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
        url = reverse('v2-admin_emailmessage-list')
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
        url = reverse('v2-admin_emailmessage-detail', args=[message.id])  + 'send/'
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
        url = reverse('v2-admin_emailmessage-detail', args=[message.id])  + 'send/'
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
        url = reverse('v2-admin_emailtemplate-list')
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

        url = reverse('v2-admin_emailtemplate-list')
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

        url = reverse('v2-admin_emailtemplate-detail', args=[template.id])
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
        url = reverse('v2-admin_emailtemplate-list')
        self.user_login.become_admin_user()
        response = self.client.post(url, format='json', data=template_dict)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = EmailTemplate.objects.first()
        self.assertEqual('error-template', created.name)


class AdminLandoConnectionViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):
    BASE_NAME = 'v2-admin_landoconnection'
    MODEL_CLS = LandoConnection

    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/lando-connections/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/lando-connections/3/')

    def create_model_object(self):
        model_object = LandoConnection.objects.create(
            cluster_type=LandoConnection.K8S_TYPE,
            host='somehost',
            username='user1',
            password='secret',
            queue_name='lando'
        )
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['cluster_type'], 'k8s')

    def build_post_data(self):
        return {
            'cluster_type': LandoConnection.K8S_TYPE,
            'host': 'somehost',
            'username': 'user1',
            'password': 'secret',
            'queue_name': 'lando'
        }


class AdminJobStrategyViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):
    BASE_NAME = 'v2-admin_jobstrategy'
    MODEL_CLS = JobStrategy

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.job_flavor = JobFlavor.objects.create(name='large')
        self.lando_connection = LandoConnection.objects.create(
            cluster_type=LandoConnection.K8S_TYPE,
            host='somehost',
            username='user1',
            password='secret',
            queue_name='lando'
        )
        self.job_settings = JobSettings.objects.create(
            lando_connection=self.lando_connection,
            job_runtime_k8s=JobRuntimeK8s.objects.create())

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/job-strategies/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/job-strategies/3/')

    def create_model_object(self):
        model_object = JobStrategy.objects.create(
            name='mystrategy',
            job_settings=self.job_settings,
            job_flavor=self.job_flavor
        )
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['name'], 'mystrategy')

    def build_post_data(self):
        return {
            'name': 'mystrategy',
            'job_settings': self.job_settings.id,
            'job_flavor': self.job_flavor.id
        }

    def test_delete_fails_with_admin_user(self):
        # Admin users are allowed to delete, overriding this test so it will not fail
        pass

    def test_delete_succeeds_with_admin_user(self):
        model_object = self.create_model_object()
        self.user_login.become_admin_user()
        url = self.object_url(model_object.id)
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_list_filter_by_name(self):
        JobStrategy.objects.create(name='default', job_flavor=self.job_flavor, job_settings=self.job_settings)
        JobStrategy.objects.create(name='better', job_flavor=self.job_flavor, job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-jobstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['name'] for item in response.data]), set(['default', 'better']))
        response = self.client.get(url + "?name=better", format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(set([item['name'] for item in response.data]), set(['better']))


class AdminJobSettingsViewSetTestCase(APITestCase, AdminCreateListRetrieveMixin):
    BASE_NAME = 'v2-admin_jobsettings'
    MODEL_CLS = JobSettings

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.job_flavor = JobFlavor.objects.create(name='large')
        self.lando_connection = LandoConnection.objects.create(
            cluster_type=LandoConnection.K8S_TYPE,
            host='somehost',
            username='user1',
            password='secret',
            queue_name='lando'
        )
        self.runtime_k8s = JobRuntimeK8s.objects.create()

    def test_list_url(self):
        self.assertEqual(self.list_url(), '/api/v2/admin/job-settings/')

    def test_object_url(self):
        self.assertEqual(self.object_url(3), '/api/v2/admin/job-settings/3/')

    def create_model_object(self):
        model_object = JobSettings.objects.create(
            name='mysettings',
            lando_connection=self.lando_connection,
            job_runtime_k8s=self.runtime_k8s)
        return model_object

    def check_single_response(self, model_object, response_data):
        self.assertEqual(response_data['id'], model_object.id)
        self.assertEqual(response_data['name'], 'mysettings')

    def build_post_data(self):
        return {
            'name': 'mysettings',
            'lando_connection': self.lando_connection.id,
            'job_runtime_k8s': self.runtime_k8s.id
        }
