import json
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from data.tests_api import UserLogin
from data.models import Workflow, WorkflowVersion, WorkflowConfiguration, JobStrategy, ShareGroup, JobFlavor, \
    JobSettings, CloudSettings, VMProject, JobFileStageGroup, DDSUserCredential, DDSEndpoint, Job
from bespin_api_v2.jobtemplate import STRING_VALUE_PLACEHOLDER, INT_VALUE_PLACEHOLDER, \
    REQUIRED_ERROR_MESSAGE, PLACEHOLDER_ERROR_MESSAGE


class AdminWorkflowViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-admin_workflow-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_not_admin_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-admin_workflow-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_with_admin_user(self):
        workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflow-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], workflow.id)
        self.assertEqual(response.data[0]['name'], 'Exome Seq')
        self.assertEqual(response.data[0]['tag'], 'exomeseq')

    def test_retrieve_with_admin_user(self):
        workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflow-list') + str(workflow.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], workflow.id)
        self.assertEqual(response.data['name'], 'Exome Seq')
        self.assertEqual(response.data['tag'], 'exomeseq')

    def test_create_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflow-list')
        response = self.client.post(url, format='json', data={
            'name': 'Exome Seq',
            'tag': 'exomeseq',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Exome Seq')
        self.assertEqual(response.data['tag'], 'exomeseq')
        workflows = Workflow.objects.all()
        self.assertEqual(len(workflows), 1)
        self.assertEqual(workflows[0].name, 'Exome Seq')
        self.assertEqual(workflows[0].tag, 'exomeseq')

    def test_put_fails_with_admin_user(self):
        workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflow-list') + str(workflow.id) + '/'
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_admin_user(self):
        workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflow-list') + str(workflow.id) + '/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AdminWorkflowVersionViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-admin_workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_not_admin_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-admin_workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_with_admin_user(self):
        workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version=1,
            url='',
            fields=[{"name":"threads", "class": "int"}],
        )
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], workflow_version.id)
        self.assertEqual(response.data[0]['workflow'], self.workflow.id)
        self.assertEqual(response.data[0]['description'], 'v1 exomeseq')
        self.assertEqual(response.data[0]['version'], 1)
        self.assertEqual(response.data[0]['fields'], [{"name": "threads", "class": "int"}])

    def test_retrieve_with_admin_user(self):
        workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version=1,
            url='',
            fields=[{"name":"threads", "class": "int"}],
        )
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list') + str(workflow_version.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], workflow_version.id)
        self.assertEqual(response.data['workflow'], self.workflow.id)
        self.assertEqual(response.data['description'], 'v1 exomeseq')
        self.assertEqual(response.data['fields'], [{"name": "threads", "class": "int"}])

    def test_create_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list')
        response = self.client.post(url, format='json', data={
            'workflow': self.workflow.id,
            'description': 'v1 exomseq',
            'version': 2,
            'url': 'https://someurl.com',
            'fields': [{"name":"threads", "class": "int"}],

        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['description'], 'v1 exomseq')
        self.assertEqual(response.data['enable_ui'], False)
        workflow_versions = WorkflowVersion.objects.all()
        self.assertEqual(len(workflow_versions), 1)
        self.assertEqual(workflow_versions[0].version, 2)
        self.assertEqual(workflow_versions[0].fields, [{"name": "threads", "class": "int"}])

    def test_put_fails_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list') + '1/'
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowversion-list') + '1/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AdminWorkflowConfigurationViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version=1,
            url='',
            fields=[{"name": "threads", "class": "int"}]
        )
        job_flavor = JobFlavor.objects.create(name='large')
        vm_project = VMProject.objects.create()
        job_settings = JobSettings.objects.create()

        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=job_flavor, job_settings=job_settings)
        self.share_group = ShareGroup.objects.create()

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-admin_workflowconfiguration-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_not_admin_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-admin_workflowconfiguration-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_with_admin_user(self):
        workflow_configuration = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A":"B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowconfiguration-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], workflow_configuration.id)
        self.assertEqual(response.data[0]['tag'], 'b37xGen')
        self.assertEqual(response.data[0]['workflow'], self.workflow.id)
        self.assertEqual(response.data[0]['system_job_order'], {"A": "B"})
        self.assertEqual(response.data[0]['default_vm_strategy'], self.job_strategy.id)
        self.assertEqual(response.data[0]['share_group'], self.share_group.id)

    def test_retrieve_with_admin_user(self):
        workflow_configuration = WorkflowConfiguration.objects.create(
            tag='b37xGen',
            workflow=self.workflow,
            system_job_order={"A": "B"},
            default_job_strategy=self.job_strategy,
            share_group=self.share_group,
        )
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowconfiguration-list') + str(workflow_configuration.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], workflow_configuration.id)
        self.assertEqual(response.data['tag'], 'b37xGen')
        self.assertEqual(response.data['workflow'], self.workflow.id)
        self.assertEqual(response.data['system_job_order'], {"A": "B"})
        self.assertEqual(response.data['default_vm_strategy'], self.job_strategy.id)
        self.assertEqual(response.data['share_group'], self.share_group.id)

    def test_create_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowconfiguration-list')
        response = self.client.post(url, format='json', data={
            'workflow': self.workflow.id,
            'tag': 'b37xGen',
            'system_job_order': {"A": "B"},
            'default_vm_strategy': self.job_strategy.id,
            'share_group': self.share_group.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tag'], 'b37xGen')
        self.assertEqual(response.data['workflow'], self.workflow.id)
        self.assertEqual(response.data['system_job_order'], {"A": "B"})
        self.assertEqual(response.data['default_vm_strategy'], self.job_strategy.id)
        self.assertEqual(response.data['share_group'], self.share_group.id)

    def test_put_fails_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowconfiguration-list') + '1/'
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_admin_user(self):
        self.user_login.become_admin_user()
        url = reverse('v2-admin_workflowconfiguration-list') + '1/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class VMStrategyViewSetTestCase(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.job_flavor = JobFlavor.objects.create(name='large')
        self.job_settings = JobSettings.objects.create()

    def test_list_fails_unauthenticated(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-vmstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_normal_user(self):
        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=self.job_flavor,
                                                     job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-vmstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.job_strategy.id)
        self.assertEqual(response.data[0]['name'], 'default')
        self.assertEqual(response.data[0]['vm_flavor']['name'], 'large')
        self.assertEqual(response.data[0]['vm_settings'], self.job_settings.id)

    def test_list_filtering(self):
        JobStrategy.objects.create(name='default', job_flavor=self.job_flavor, job_settings=self.job_settings)
        JobStrategy.objects.create(name='better', job_flavor=self.job_flavor, job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-vmstrategies-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['name'] for item in response.data]), set(['default', 'better']))
        url = reverse('v2-vmstrategies-list') + "?name=better"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(set([item['name'] for item in response.data]), set(['better']))

    def test_retrieve_with_normal_user(self):
        self.job_strategy = JobStrategy.objects.create(name='default', job_flavor=self.job_flavor,
                                                     job_settings=self.job_settings)
        self.user_login.become_normal_user()
        url = reverse('v2-vmstrategies-list') + str(self.job_strategy.id) + '/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.job_strategy.id)
        self.assertEqual(response.data['name'], 'default')
        self.assertEqual(response.data['vm_flavor']['id'], self.job_flavor.id)
        self.assertEqual(response.data['vm_settings'], self.job_settings.id)

    def test_post_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-vmstrategies-list') + '1/'
        response = self.client.post(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-vmstrategies-list') + '1/'
        response = self.client.put(url, format='json', data={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_fails_with_normal_user(self):
        self.user_login.become_normal_user()
        url = reverse('v2-vmstrategies-list') + '1/'
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
            version=1,
            url='',
            fields=[{"name":"threads", "type": "int"},{"name":"items", "type": "int"}],
        )
        self.workflow_version2 = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v2 exomeseq',
            version=2,
            url='',
            fields=[{"name":"threads", "type": "int"}],
        )
        job_flavor = JobFlavor.objects.create(name='large')
        job_settings = JobSettings.objects.create()

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
        self.assertEqual(response.data[0]['default_vm_strategy'], self.job_strategy.id)
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
        self.assertEqual(response.data['default_vm_strategy'], self.job_strategy.id)
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
            version=1,
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
        )
        job_flavor = JobFlavor.objects.create(name='large')
        vm_project = VMProject.objects.create()
        job_settings = JobSettings.objects.create()

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
            'job_vm_strategy': self.job_strategy.id,
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


class WorkflowVersionsViewSet(APITestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.workflow = Workflow.objects.create(name='Exome Seq', tag='exomeseq')
        self.workflow2 = Workflow.objects.create(name='Microbiome', tag='microbiome')
        self.workflow_version1 = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v1 exomeseq',
            version=1,
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
        )
        self.workflow_version2 = WorkflowVersion.objects.create(
            workflow=self.workflow,
            description='v2 exomeseq',
            version=2,
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
            enable_ui=False,
        )
        self.workflow_version3 = WorkflowVersion.objects.create(
            workflow=self.workflow2,
            description='v1 other',
            version=1,
            url='',
            fields=[{"name": "threads", "type": "int"}, {"name": "items", "type": "string"}],
        )

    def test_list_filtering(self):
        user = self.user_login.become_normal_user()
        url = reverse('v2-workflowversion-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        url = reverse('v2-workflowversion-list') + '?workflow__tag=exomeseq'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set([item['description'] for item in response.data]), set(['v1 exomeseq', 'v2 exomeseq']))

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
