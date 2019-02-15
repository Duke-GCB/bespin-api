from django.test import TestCase
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.exceptions import ValidationError
from unittest.mock import MagicMock, patch, Mock
from data.models import DDSEndpoint, DDSUserCredential, Workflow, WorkflowVersion, JobFileStageGroup, ShareGroup, \
    DDSJobInputFile, URLJobInputFile, JobFlavor, VMProject, VMSettings, CloudSettings, Job
from data.jobfactory import JobFactory, JobFactoryException, JobVMStrategy, calculate_stage_group_size, \
    calculate_volume_size
import json


FLY_RNASEQ_URL = "https://raw.githubusercontent.com/Duke-GCB/bespin-cwl/master/packed-workflows/rnaseq-pt1-packed.cwl"


class JobFactoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_user')
        self.endpoint = DDSEndpoint.objects.create(name='app1', agent_key='abc123')
        self.worker_cred = DDSUserCredential.objects.create(user=self.user, token='abc123', endpoint=self.endpoint)
        workflow = Workflow.objects.create(name='RnaSeq')
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               object_name='#main',
                                                               version='1',
                                                               url=FLY_RNASEQ_URL,
                                                               fields=[])
        self.stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.share_group = ShareGroup.objects.create(name='result data checkers')
        vm_project = VMProject.objects.create(name='project1')
        cloud_settings = CloudSettings.objects.create(name='cloud1', vm_project=vm_project)
        self.vm_settings = VMSettings.objects.create(name='settings1', cloud_settings=cloud_settings)
        self.job_flavor = JobFlavor.objects.create(name='flavor1')
        self.volume_mounts = json.dumps({'/dev/vdb1': '/work'})
        self.job_vm_strategy = JobVMStrategy(self.vm_settings, self.job_flavor,
                                             volume_size_base=10, volume_size_factor=0,
                                             volume_mounts=self.volume_mounts)

    def test_creates_job_with_empty_job_order_data(self):
        user_job_order = {}
        system_job_order = {}
        self.job_vm_strategy.volume_size_factor = 0
        self.job_vm_strategy.volume_size_base = 150
        job_factory = JobFactory(user=self.user, workflow_version=self.workflow_version,
                                 job_name='Test Job', fund_code='123-4', stage_group=self.stage_group,
                                 system_job_order=system_job_order, user_job_order=user_job_order,
                                 job_vm_strategy=self.job_vm_strategy, share_group=self.share_group)
        job = job_factory.create_job()
        self.assertEqual(json.loads(job.job_order), {})

    @override_settings(REQUIRE_JOB_TOKENS=True)
    def test_creates_job(self):
        user_job_order = {'input1': 'user'}
        system_job_order = {'input2': 'system'}
        self.job_vm_strategy.volume_size_factor = 0
        self.job_vm_strategy.volume_size_base = 110
        job_factory = JobFactory(user=self.user, workflow_version=self.workflow_version,
                                 job_name='Test Job', fund_code='123-4', stage_group=self.stage_group,
                                 system_job_order=system_job_order, user_job_order=user_job_order,
                                 job_vm_strategy=self.job_vm_strategy, share_group=self.share_group)
        job = job_factory.create_job()
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.workflow_version, self.workflow_version)
        expected_job_order = {'input1':'user','input2':'system'}
        self.assertEqual(expected_job_order, json.loads(job.job_order))
        self.assertEqual(job.name, 'Test Job')
        self.assertEqual(job.vm_settings, self.vm_settings)
        self.assertEqual(job.job_flavor, self.job_flavor)
        self.assertEqual(self.worker_cred.id, job.output_project.dds_user_credentials.id)
        self.assertEqual(job.volume_size, 110)
        self.assertEqual(job.vm_volume_mounts, self.volume_mounts)
        self.assertEqual(job.share_group, self.share_group)
        self.assertEqual(job.fund_code, '123-4')
        self.assertEqual(job.state, Job.JOB_STATE_NEW)

    @override_settings(REQUIRE_JOB_TOKENS=False)
    def test_creates_job_is_authorized(self):
        user_job_order = {'input1': 'user'}
        system_job_order = {'input2': 'system'}
        self.job_vm_strategy.volume_size_factor = 0
        self.job_vm_strategy.volume_size_base = 110
        job_factory = JobFactory(user=self.user, workflow_version=self.workflow_version,
                                 job_name='Test Job', fund_code='123-4', stage_group=self.stage_group,
                                 system_job_order=system_job_order, user_job_order=user_job_order,
                                 job_vm_strategy=self.job_vm_strategy, share_group=self.share_group)
        job = job_factory.create_job()
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.workflow_version, self.workflow_version)
        self.assertEqual(job.state, Job.JOB_STATE_AUTHORIZED)

    def test_favors_user_inputs(self):
        user_job_order = {'input1': 'user'}
        system_job_order = {'input1': 'system'}
        self.job_vm_strategy.volume_size_factor = 0
        self.job_vm_strategy.volume_size_base = 120
        job_factory = JobFactory(user=self.user, workflow_version=self.workflow_version,
                                 job_name='Test Job', fund_code='123-4', stage_group=self.stage_group,
                                 system_job_order=system_job_order, user_job_order=user_job_order,
                                 job_vm_strategy=self.job_vm_strategy, share_group=self.share_group)
        job = job_factory.create_job()
        expected_job_order = json.dumps({'input1':'user'})
        self.assertEqual(expected_job_order, job.job_order)

    def test_calculate_stage_group_size(self):
        stage_group = JobFileStageGroup.objects.create(user=self.user)
        dds_file_sizes = [10 * 1024 * 1024,  # 10 MB
                          2.5 * 1024 * 1024 * 1024,  # 2.5 GB
                          ]
        url_file_sizes = [0.5 * 1024 * 1024 * 1024]  # 0.5 GB
        for size in dds_file_sizes:
            DDSJobInputFile.objects.create(stage_group=stage_group, dds_user_credentials=self.worker_cred, size=size)
        for size in url_file_sizes:
            URLJobInputFile.objects.create(stage_group=stage_group, size=size)
        self.assertEqual(3.00977, round(calculate_stage_group_size(stage_group), 5))

    @patch('data.jobfactory.calculate_stage_group_size')
    def test_calculate_volume_size(self, mock_calculate_stage_group_size):
        mock_calculate_stage_group_size.return_value = 20
        volume_size_base = 10
        volume_size_factor = 4
        stage_group = Mock()
        self.assertEqual(4 * 20 + 10, calculate_volume_size(volume_size_base, volume_size_factor, stage_group))
