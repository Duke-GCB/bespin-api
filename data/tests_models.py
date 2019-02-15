from django.test import TestCase
from data.models import DDSEndpoint, DDSUserCredential
from data.models import Workflow, WorkflowVersion
from data.models import Job, JobFileStageGroup, DDSJobInputFile, URLJobInputFile, JobDDSOutputProject, JobError
from data.models import LandoConnection
from data.models import JobQuestionnaire, JobQuestionnaireType, JobAnswerSet, JobFlavor, VMProject, JobSettings, \
    CloudSettings, VMCommand
from data.models import JobToken
from data.models import DDSUser, ShareGroup, WorkflowMethodsDocument
from data.models import EmailTemplate, EmailMessage
from data.models import JobActivity
from data.models import JobStrategy, WorkflowConfiguration
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
import json

CWL_URL = 'https://raw.githubusercontent.com/johnbradley/iMADS-worker/master/predict_service/predict-workflow-packed.cwl'


class DDSEndpointTests(TestCase):
    # Not validating blank or null fields here, as it does not happen at the model layer
    # It is the responsibility of a form or serializer to do that.

    def test_unique_parameters1(self):
        endpoint1 = DDSEndpoint.objects.create(name='endpoint1', agent_key='abc123')
        self.assertIsNotNone(endpoint1)
        endpoint2 = DDSEndpoint.objects.create(name='endpoint2', agent_key='def456')
        self.assertIsNotNone(endpoint2)
        self.assertNotEqual(endpoint1, endpoint2)
        with self.assertRaises(IntegrityError):
            DDSEndpoint.objects.create(name='endpoint3', agent_key=endpoint1.agent_key)

    def test_unique_parameters2(self):
        DDSEndpoint.objects.create(name='endpoint1', agent_key='abc123')
        with self.assertRaises(IntegrityError):
            DDSEndpoint.objects.create(name='endpoint1', agent_key='ghi789')


class DDSUserCredentialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_user')
        self.endpoint = DDSEndpoint.objects.create(name='app1', agent_key='abc123')
        self.endpoint2 = DDSEndpoint.objects.create(name='app2', agent_key='abc124')

    def test_unique_parameters1(self):
        DDSUserCredential.objects.create(user=self.user, token='abc123', endpoint=self.endpoint)
        with self.assertRaises(IntegrityError):
            DDSUserCredential.objects.create(user=self.user, token='def456', endpoint=self.endpoint)

    def test_unique_parameters2(self):
        DDSUserCredential.objects.create(user=self.user, token='abc123', endpoint=self.endpoint)
        other_user = User.objects.create_user('other_user')
        with self.assertRaises(IntegrityError):
            DDSUserCredential.objects.create(user=other_user, token='abc123', endpoint=self.endpoint)

    def test_user_can_have_creds_for_diff_endpoints(self):
        DDSUserCredential.objects.create(user=self.user, token='abc123', endpoint=self.endpoint, dds_id='1')
        DDSUserCredential.objects.create(user=self.user, token='abc124', endpoint=self.endpoint2, dds_id='2')


class WorkflowTests(TestCase):
    def test_basic_functionality(self):
        Workflow.objects.create(name='RnaSeq', tag='rna-seq')
        workflow = Workflow.objects.first()
        self.assertEqual('RnaSeq', workflow.name)
        self.assertEqual('rna-seq', workflow.tag)

    def test_tag_field_unique(self):
        Workflow.objects.create(name='RnaSeq', tag='rna-seq')
        with self.assertRaises(IntegrityError):
            Workflow.objects.create(name='RnaSeq2', tag='rna-seq')


class WorkflowVersionTests(TestCase):
    def setUp(self):
        self.workflow = Workflow.objects.create(name='RnaSeq')

    def test_basic_functionality(self):
        WorkflowVersion.objects.create(workflow=self.workflow,
                                       object_name='#main',
                                       version='1',
                                       url=CWL_URL,
                                       fields=[])
        workflow_version = WorkflowVersion.objects.first()
        self.assertEqual(self.workflow, workflow_version.workflow)
        self.assertEqual('#main', workflow_version.object_name)
        self.assertEqual(1, workflow_version.version)
        self.assertEqual(CWL_URL, workflow_version.url)
        self.assertIsNotNone(workflow_version.created)
        self.assertEqual(workflow_version.enable_ui, True)

    def test_create_disable_ui(self):
        WorkflowVersion.objects.create(workflow=self.workflow,
                                       object_name='#main',
                                       version='1',
                                       url=CWL_URL,
                                       fields=[],
                                       enable_ui=False)
        workflow_version = WorkflowVersion.objects.first()
        self.assertEqual(workflow_version.enable_ui, False)

    def test_default_object_name(self):
        WorkflowVersion.objects.create(workflow=self.workflow,
                                       version='1',
                                       url=CWL_URL,
                                       fields=[])
        workflow_version = WorkflowVersion.objects.first()
        self.assertEqual('#main', workflow_version.object_name)

    def test_create_with_description(self):
        desc = """This is a detailed description of the job."""
        WorkflowVersion.objects.create(workflow=self.workflow, description=desc, version=1, fields=[])
        wv = WorkflowVersion.objects.first()
        self.assertEqual(desc, wv.description)

    def test_version_num_and_workflow_are_unique(self):
        WorkflowVersion.objects.create(workflow=self.workflow, description="one", version=1, fields=[])
        with self.assertRaises(IntegrityError):
            WorkflowVersion.objects.create(workflow=self.workflow, description="two", version=1)

    def test_sorted_by_version_num(self):
        WorkflowVersion.objects.create(workflow=self.workflow, description="two", version=2, fields=[])
        a_workflow_version = WorkflowVersion.objects.create(workflow=self.workflow, description="one", version=1,
                                                            fields=[])
        WorkflowVersion.objects.create(workflow=self.workflow, description="three", version=3, fields=[])
        versions = [wv.version for wv in WorkflowVersion.objects.all()]
        self.assertEqual([1, 2, 3], versions)
        a_workflow_version.version = 4
        a_workflow_version.save()
        versions = [wv.version for wv in WorkflowVersion.objects.all()]
        self.assertEqual([2, 3, 4], versions)


class JobTests(TestCase):
    def setUp(self):
        workflow = Workflow.objects.create(name='RnaSeq')
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               object_name='#main',
                                                               version='1',
                                                               url=CWL_URL,
                                                               fields=[])
        self.user = User.objects.create_user('test_user')
        self.sample_json = "{'type': 1}"
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.job_flavor = JobFlavor.objects.create(name='flavor1')
        vm_project = VMProject.objects.create(name='project1')
        cloud_settings = CloudSettings.objects.create(vm_project=vm_project)
        self.job_settings = JobSettings.objects.create()

    def test_create(self):
        Job.objects.create(workflow_version=self.workflow_version, user=self.user,
                           job_order=self.sample_json,
                           share_group=self.share_group,
                           job_settings=self.job_settings,
                           job_flavor=self.job_flavor)
        job = Job.objects.first()
        self.assertEqual(self.workflow_version, job.workflow_version)
        self.assertEqual(self.user, job.user)
        self.assertIsNotNone(job.created)
        self.assertEqual(Job.JOB_STATE_NEW, job.state)
        self.assertIsNotNone(job.last_updated)
        self.assertEqual(job.vm_instance_name, '')
        self.assertEqual(job.vm_volume_name, '')
        self.assertEqual(self.job_settings, job.job_settings)
        self.assertIsNone(job.run_token)
        self.assertEqual(self.share_group, job.share_group)
        self.assertEqual(True, job.cleanup_vm)
        activities = JobActivity.objects.all()

    def test_create_with_cleanup_vm(self):
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 user=self.user,
                                 job_order=self.sample_json,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 cleanup_vm=True)
        self.assertEqual(True, job.cleanup_vm)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 user=self.user,
                                 job_order=self.sample_json,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 cleanup_vm=False)
        self.assertEqual(False, job.cleanup_vm)

    def test_create_with_name(self):
        Job.objects.create(name='Rna Seq for B-Lab', user=self.user, share_group=self.share_group, job_settings=self.job_settings,
                           job_flavor=self.job_flavor)
        job = Job.objects.first()
        self.assertEqual('Rna Seq for B-Lab', job.name)

    def test_state_changes(self):
        # Create job which should start in new state
        Job.objects.create(workflow_version=self.workflow_version, user=self.user, job_order=self.sample_json,
                           share_group=self.share_group, job_settings=self.job_settings, job_flavor=self.job_flavor,
                           )
        job = Job.objects.first()
        self.assertEqual(Job.JOB_STATE_NEW, job.state)

        # User enters token (authorizes running job)
        job.state = Job.JOB_STATE_AUTHORIZED
        job.run_token = JobToken.objects.create(token='secret-1')
        job.save()
        job = Job.objects.first()

        # Set state to create VM
        job.state = Job.JOB_STATE_RUNNING
        job_created = job.created
        job_updated = job.last_updated
        job.save()
        job = Job.objects.first()
        self.assertEqual(Job.JOB_STATE_RUNNING, job.state)
        # last_updated should have changed
        self.assertEqual(job_created, job.created)
        self.assertLess(job_updated, job.last_updated)

        # Set state to canceled
        job.state = Job.JOB_STATE_CANCEL
        job.save()
        job = Job.objects.first()
        self.assertEqual(Job.JOB_STATE_CANCEL, job.state)

    @staticmethod
    def add_job_fields(obj):
        share_group = ShareGroup.objects.create(name='Results Checkers')
        obj.user = User.objects.create_user('test_user')
        obj.endpoint = DDSEndpoint.objects.create(name='app1', agent_key='abc123')
        obj.user_credentials = DDSUserCredential.objects.create(user=obj.user, token='abc123', endpoint=obj.endpoint)
        workflow = Workflow.objects.create(name='RnaSeq')
        obj.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                              object_name='#main',
                                                              version='1',
                                                              url=CWL_URL,
                                                              fields=[])
        obj.sample_json = "{'type': 1}"

        job_flavor = JobFlavor.objects.create(name='flavor1')
        vm_project = VMProject.objects.create(name='project1')
        cloud_settings = CloudSettings.objects.create(vm_project=vm_project)
        obj.job_settings = JobSettings.objects.create()

        obj.job = Job.objects.create(workflow_version=obj.workflow_version, user=obj.user,
                                     job_order=obj.sample_json,
                                     share_group=share_group,
                                     job_settings=obj.job_settings,
                                     job_flavor=job_flavor)

    def test_sorted_by_created(self):
        j1 = Job.objects.create(workflow_version=self.workflow_version,
                                user=self.user,
                                job_order=self.sample_json,
                                share_group=self.share_group,
                                job_settings=self.job_settings,
                                job_flavor=self.job_flavor,
                                )
        j2 = Job.objects.create(workflow_version=self.workflow_version,
                                user=self.user,
                                job_order=self.sample_json,
                                share_group=self.share_group,
                                job_settings=self.job_settings,
                                job_flavor=self.job_flavor,
                                )
        j3 = Job.objects.create(workflow_version=self.workflow_version,
                                user=self.user,
                                job_order=self.sample_json,
                                share_group=self.share_group,
                                job_settings=self.job_settings,
                                job_flavor=self.job_flavor,
                                )
        j4 = Job.objects.create(workflow_version=self.workflow_version,
                                user=self.user,
                                job_order=self.sample_json,
                                share_group=self.share_group,
                                job_settings=self.job_settings,
                                job_flavor=self.job_flavor,
                                )
        job_ids = [job.id for job in Job.objects.all()]
        self.assertEqual([j1.id, j2.id, j3.id, j4.id], job_ids)
        j2.delete()
        j2 = Job.objects.create(workflow_version=self.workflow_version,
                                user=self.user,
                                job_order=self.sample_json,
                                share_group=self.share_group,
                                job_settings=self.job_settings,
                                job_flavor=self.job_flavor,
                                )
        job_ids = [job.id for job in Job.objects.all()]
        self.assertEqual([j1.id, j3.id, j4.id, j2.id], job_ids)

    def test_fails_mismatch_stage_group_user(self):
        job = Job.objects.create(workflow_version=self.workflow_version, user=self.user,
                                 job_order=self.sample_json,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        other_user = User.objects.create_user('other_user')
        stage_group = JobFileStageGroup.objects.create(user=other_user)
        with self.assertRaises(ValidationError):
            job.stage_group = stage_group
            job.save()

    def test_create_with_run_job_token(self):
        job_token = JobToken.objects.create(token='test-this-1')
        job = Job.objects.create(workflow_version=self.workflow_version, user=self.user,
                                 job_order=self.sample_json,
                                 run_token=job_token,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        self.assertEqual(job.run_token, job_token)

    def test_save_then_set_run_job_token(self):
        job_token2 = JobToken.objects.create(token='test-this-2')
        job2 = Job.objects.create(workflow_version=self.workflow_version, user=self.user,
                                  job_order=self.sample_json,
                                  share_group=self.share_group,
                                  job_settings=self.job_settings,
                                  job_flavor=self.job_flavor,
                                  )
        self.assertEqual(job2.run_token, None)
        job2.run_token = job_token2
        job2.save()

    def test_jobs_cant_share_job_tokens(self):
        job_token = JobToken.objects.create(token='test-this-1')
        job = Job.objects.create(workflow_version=self.workflow_version, user=self.user,
                                 job_order=self.sample_json,
                                 run_token=job_token,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor,
                                 )
        with self.assertRaises(IntegrityError) as raised_error:
            job2 = Job.objects.create(workflow_version=self.workflow_version, user=self.user,
                                      job_order=self.sample_json,
                                      run_token=job_token,
                                      share_group=self.share_group,
                                      job_settings=self.job_settings,
                                      job_flavor=self.job_flavor,
                                      )
        self.assertIn("unique constraint", str(raised_error.exception).lower())

    def test_can_set_organize_output_project_step(self):
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 user=self.user,
                                 job_order=self.sample_json,
                                 share_group=self.share_group,
                                 job_settings=self.job_settings,
                                 job_flavor=self.job_flavor)
        job.step = Job.JOB_STEP_ORGANIZE_OUTPUT_PROJECT
        job.save()
        self.assertEqual(Job.objects.first().step, Job.JOB_STEP_ORGANIZE_OUTPUT_PROJECT)

    def test_job_activity_creation(self):
        # Create job which should start in new state
        job = Job.objects.create(workflow_version=self.workflow_version, user=self.user, job_order=self.sample_json,
                           share_group=self.share_group, job_settings=self.job_settings, job_flavor=self.job_flavor)

        def get_activity_details(job):
            return [(item.state, item.step) for item in JobActivity.objects.filter(job=job).order_by('created')]

        self.assertEqual(get_activity_details(job), [
            (Job.JOB_STATE_NEW, ''),
        ])

        # Test that a change to an unrelated field will not create an activity
        job.name = 'Some new name'
        self.assertEqual(job.should_create_activity(), False)
        job.save()
        self.assertEqual(get_activity_details(job), [
            (Job.JOB_STATE_NEW, ''),
        ])

        # test that changing state will create an activity
        job.state = Job.JOB_STATE_AUTHORIZED
        self.assertEqual(job.should_create_activity(), True)
        job.save()
        self.assertEqual(job.should_create_activity(), False)
        self.assertEqual(get_activity_details(job), [
            (Job.JOB_STATE_NEW, ''),
            (Job.JOB_STATE_AUTHORIZED, ''),
        ])

        # Test that only the most recent job activity should be checked against
        job.state = Job.JOB_STATE_NEW
        self.assertEqual(job.should_create_activity(), True)
        job.save()
        self.assertEqual(job.should_create_activity(), False)
        self.assertEqual(get_activity_details(job), [
            (Job.JOB_STATE_NEW, ''),
            (Job.JOB_STATE_AUTHORIZED, ''),
            (Job.JOB_STATE_NEW, ''),
        ])

        # Test that changing step will create a new activity
        job.step = Job.JOB_STEP_CREATE_VM
        self.assertEqual(job.should_create_activity(), True)
        job.save()
        self.assertEqual(job.should_create_activity(), False)
        self.assertEqual(get_activity_details(job), [
            (Job.JOB_STATE_NEW, ''),
            (Job.JOB_STATE_AUTHORIZED, ''),
            (Job.JOB_STATE_NEW, ''),
            (Job.JOB_STATE_NEW, Job.JOB_STEP_CREATE_VM),
        ])

        # Test debounce step changes
        job.step = Job.JOB_STEP_CREATE_VM
        self.assertEqual(job.should_create_activity(), False)
        job.save()
        self.assertEqual(get_activity_details(job), [
            (Job.JOB_STATE_NEW, ''),
            (Job.JOB_STATE_AUTHORIZED, ''),
            (Job.JOB_STATE_NEW, ''),
            (Job.JOB_STATE_NEW, Job.JOB_STEP_CREATE_VM),
        ])

    def test_record_output_project_step(self):
        job = Job.objects.create(workflow_version=self.workflow_version, user=self.user, job_order=self.sample_json,
                                 share_group=self.share_group, job_settings=self.job_settings, job_flavor=self.job_flavor)
        job.state = Job.JOB_STATE_RUNNING
        job.step = Job.JOB_STEP_RECORD_OUTPUT_PROJECT
        job.save()
        self.assertEqual(Job.objects.get(pk=job.pk).step, Job.JOB_STEP_RECORD_OUTPUT_PROJECT)


class JobFileStageGroupTests(TestCase):

    def setUp(self):
        JobTests.add_job_fields(self)

    def test_dds_file(self):
        stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.job.stage_group = stage_group
        self.job.save()
        DDSJobInputFile.objects.create(stage_group=stage_group,
                                       project_id='1234',
                                       file_id='5321',
                                       dds_user_credentials=self.user_credentials,
                                       destination_path='sample.fasta',
                                       size=10000,
                                       sequence=1)
        # Test job fields
        stage_group = JobFileStageGroup.objects.first()
        self.assertEqual(self.job, stage_group.job)
        self.assertEqual(self.user, stage_group.user)

        # Test dds_files
        dds_files = stage_group.dds_files.all()
        self.assertEqual(1, len(dds_files))
        dds_file = dds_files[0]
        self.assertEqual(stage_group, dds_file.stage_group)
        self.assertEqual('1234', dds_file.project_id)
        self.assertEqual(self.user_credentials, dds_file.dds_user_credentials)
        self.assertEqual('sample.fasta', dds_file.destination_path)
        self.assertEqual(10000, dds_file.size)
        self.assertEqual(1, dds_file.sequence)

    def test_dds_file_sequence_stage_group_unique(self):
        stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.job.stage_group = stage_group
        self.job.save()
        DDSJobInputFile.objects.create(stage_group=stage_group,
                                       project_id='1234',
                                       file_id='5321',
                                       dds_user_credentials=self.user_credentials,
                                       destination_path='sample.fasta',
                                       size=10000,
                                       sequence_group=1,
                                       sequence=1)
        DDSJobInputFile.objects.create(stage_group=stage_group,
                                       project_id='1234',
                                       file_id='5321',
                                       dds_user_credentials=self.user_credentials,
                                       destination_path='sample.fasta',
                                       size=10000,
                                       sequence_group=1,
                                       sequence=2)
        with self.assertRaises(IntegrityError):
            DDSJobInputFile.objects.create(stage_group=stage_group,
                                           project_id='1234',
                                           file_id='5321',
                                           dds_user_credentials=self.user_credentials,
                                           destination_path='sample.fasta',
                                           size=10000,
                                           sequence_group=1,
                                           sequence=1)

    def test_url_file(self):
        stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.job.stage_group = stage_group
        self.job.save()
        URLJobInputFile.objects.create(stage_group=stage_group,
                                       url='https://data.org/sample.fasta',
                                       destination_path='sample.fasta',
                                       size=20000,
                                       sequence=1)

        # Test job fields
        stage_group = JobFileStageGroup.objects.first()
        self.assertEqual(self.job, stage_group.job)
        self.assertEqual(self.user, stage_group.user)

        # Test dds_files
        url_files = stage_group.url_files.all()
        self.assertEqual(1, len(url_files))
        url_file = url_files[0]
        self.assertEqual(stage_group, url_file.stage_group)
        self.assertEqual('https://data.org/sample.fasta', url_file.url)
        self.assertEqual('sample.fasta', url_file.destination_path)
        self.assertEqual(20000, url_file.size)
        self.assertEqual(1, url_file.sequence)

    def test_url_file_sequence_stage_group_unique(self):
        stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.job.stage_group = stage_group
        self.job.save()
        URLJobInputFile.objects.create(stage_group=stage_group,
                                       url='https://data.org/sample.fasta',
                                       destination_path='sample.fasta',
                                       size=20000,
                                       sequence_group=1,
                                       sequence=1)
        URLJobInputFile.objects.create(stage_group=stage_group,
                                       url='https://data.org/sample.fasta',
                                       destination_path='sample.fasta',
                                       size=20000,
                                       sequence_group=1,
                                       sequence=2)
        with self.assertRaises(IntegrityError):
            URLJobInputFile.objects.create(stage_group=stage_group,
                                           url='https://data.org/sample.fasta',
                                           destination_path='sample.fasta',
                                           size=20000,
                                           sequence_group=1,
                                           sequence=1)


class JobDDSOutputProjectTests(TestCase):
    def setUp(self):
        JobTests.add_job_fields(self)

    def test_basic_functionality(self):
        JobDDSOutputProject.objects.create(job=self.job, project_id='1234',
                                           dds_user_credentials=self.user_credentials)
        job_output_project = JobDDSOutputProject.objects.first()
        self.assertEqual(self.job, job_output_project.job)
        self.assertEqual('1234', job_output_project.project_id)
        self.assertEqual(self.user_credentials, job_output_project.dds_user_credentials)


class LandoConnectionTests(TestCase):
    def test_basic_functionality(self):
        LandoConnection.objects.create(host='10.109.253.74', username='jpb67', password='secret', queue_name='lando')
        connection = LandoConnection.objects.first()
        self.assertEqual('10.109.253.74', connection.host)
        self.assertEqual('jpb67', connection.username)
        self.assertEqual('secret', connection.password)
        self.assertEqual('lando', connection.queue_name)


class JobErrorTests(TestCase):
    def setUp(self):
        JobTests.add_job_fields(self)

    def test_basic_functionality(self):
        JobError.objects.create(job=self.job,
                                content="Openstack ran out of floating IPs.",
                                job_step=Job.JOB_STEP_CREATE_VM)
        job_error = JobError.objects.first()
        self.assertEqual(self.job, job_error.job)
        self.assertEqual("Openstack ran out of floating IPs.", job_error.content)
        self.assertEqual(Job.JOB_STEP_CREATE_VM, job_error.job_step)
        self.assertIsNotNone(job_error.created)


class JobQuestionnaireTests(TestCase):

    @staticmethod
    def add_vmsettings_fields(obj):
        obj.vm_project = VMProject.objects.create(name='project')
        obj.cloud_settings = CloudSettings.objects.create(name='cloud', vm_project=obj.vm_project)
        obj.job_settings = JobSettings.objects.create(name='settings')
        obj.job_flavor = JobFlavor.objects.create(name='flavor')

    @staticmethod
    def add_workflowversion_fields(obj):
        obj.user = User.objects.create_user('user')
        obj.workflow = Workflow.objects.create(name='RnaSeq', tag='rna-seq')
        obj.workflow_version = WorkflowVersion.objects.create(workflow=obj.workflow,
                                                              object_name='#main',
                                                              version='1',
                                                              url=CWL_URL,
                                                              fields=[])
        obj.flavor1 = JobFlavor.objects.create(name='flavor1')
        obj.flavor2 = JobFlavor.objects.create(name='flavor2')
        obj.project = VMProject.objects.create(name='bespin-project')

    def setUp(self):
        self.add_workflowversion_fields(self)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.cloud = CloudSettings.objects.create(name='cloud',
                                                  vm_project=self.project)
        self.settings1 = JobSettings.objects.create(name='settings1')
        self.settings2 = JobSettings.objects.create(name='settings2')
        self.questionnaire_type = JobQuestionnaireType.objects.create(tag='human')

    def test_two_questionnaires(self):
        questionnaire = JobQuestionnaire.objects.create(name='Ant RnaSeq',
                                                        description='Uses reference genome xyz and gene index abc',
                                                        workflow_version=self.workflow_version,
                                                        system_job_order_json='{"system_input": "foo"}',
                                                        share_group=self.share_group,
                                                        job_settings=self.settings1,
                                                        job_flavor=self.flavor1,
                                                        volume_size_base=10,
                                                        volume_size_factor=5,
                                                        type=self.questionnaire_type
                                                        )
        questionnaire = JobQuestionnaire.objects.create(name='Human RnaSeq',
                                                        description='Uses reference genome zew and gene index def',
                                                        workflow_version=self.workflow_version,
                                                        system_job_order_json='{"system_input":"bar"}',
                                                        share_group=self.share_group,
                                                        job_settings=self.settings2,
                                                        job_flavor=self.flavor2,
                                                        volume_size_base=3,
                                                        volume_size_factor=2,
                                                        type=self.questionnaire_type
                                                        )
        ant_questionnaire = JobQuestionnaire.objects.filter(name='Ant RnaSeq').first()
        self.assertEqual('Ant RnaSeq', ant_questionnaire.name)
        self.assertEqual('Uses reference genome xyz and gene index abc', ant_questionnaire.description)
        self.assertEqual('foo',json.loads(ant_questionnaire.system_job_order_json)['system_input'])
        self.assertEqual('flavor1', ant_questionnaire.job_flavor.name)
        #self.assertEqual('bespin-project', ant_questionnaire.job_settings.cloud_settings.vm_project.name)
        self.assertEqual(self.share_group, ant_questionnaire.share_group)
        self.assertEqual(10, ant_questionnaire.volume_size_base)
        self.assertEqual(5, ant_questionnaire.volume_size_factor)

        human_questionnaire = JobQuestionnaire.objects.filter(name='Human RnaSeq').first()
        self.assertEqual('Human RnaSeq', human_questionnaire.name)
        self.assertEqual('Uses reference genome zew and gene index def', human_questionnaire.description)
        self.assertEqual('bar',json.loads(human_questionnaire.system_job_order_json)['system_input'])
        self.assertEqual('flavor2', human_questionnaire.job_flavor.name)
        # TODO self.assertEqual('bespin-project', human_questionnaire.job_settings.cloud_settings.vm_project.name)
        self.assertEqual(self.share_group, human_questionnaire.share_group)
        self.assertEqual(3, human_questionnaire.volume_size_base)
        self.assertEqual(2, human_questionnaire.volume_size_factor)

    def test_make_tag(self):
        questionnaire = JobQuestionnaire.objects.create(name='Ant RnaSeq',
                                                        description='Uses reference genome xyz and gene index abc',
                                                        workflow_version=self.workflow_version,
                                                        system_job_order_json='{"system_input": "foo"}',
                                                        share_group=self.share_group,
                                                        job_settings=self.settings1,
                                                        job_flavor=self.flavor1,
                                                        volume_size_base=10,
                                                        volume_size_factor=5,
                                                        type=self.questionnaire_type
                                                        )
        self.assertEqual(questionnaire.make_tag(), 'rna-seq/v1/human')
        self.assertEqual(JobQuestionnaire.split_tag_parts(questionnaire.make_tag()), ('rna-seq', 1, 'human'))

    def test_split_tag_parts(self):
        data = {
            ("stuff", None),
            ("exome/v1", None),
            ("exome/v1/human", ("exome", 1, "human")),
            ("exome/v1/human/other", None),
        }
        for tag, expected_parts in data:
            self.assertEqual(JobQuestionnaire.split_tag_parts(tag=tag), expected_parts)


class JobAnswerSetTests(TestCase):

    def setUp(self):
        JobQuestionnaireTests.add_workflowversion_fields(self)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        JobQuestionnaireTests.add_vmsettings_fields(self)
        self.questionnaire_type = JobQuestionnaireType.objects.create(tag='human')
        self.questionnaire = JobQuestionnaire.objects.create(name='Exome Seq Q',
                                                             description='Uses reference genome xyz and gene index abc',
                                                             workflow_version=self.workflow_version,
                                                             system_job_order_json='{"system_input": "foo"}',
                                                             share_group=self.share_group,
                                                             job_settings=self.job_settings,
                                                             job_flavor=self.job_flavor,
                                                             type=self.questionnaire_type,
                                                             )

    def test_basic_functionality(self):
        JobAnswerSet.objects.create(user=self.user,
                                    questionnaire=self.questionnaire,
                                    job_name='job 1',
                                    user_job_order_json='{"user_input":"bar"}'
        )
        job_answer_set = JobAnswerSet.objects.first()
        self.assertEqual(self.user, job_answer_set.user),
        self.assertEqual(self.questionnaire, job_answer_set.questionnaire)
        self.assertEqual('job 1', job_answer_set.job_name)
        self.assertEqual('{"user_input":"bar"}', job_answer_set.user_job_order_json)


    def test_fails_mismatch_stage_group_user(self):
        job_answer_set = JobAnswerSet.objects.create(user=self.user,
                                                     questionnaire=self.questionnaire,
                                                     job_name='job 2',
                                                     user_job_order_json='{"user_input":"bar"}'
        )
        other_user = User.objects.create_user('other_user')
        stage_group = JobFileStageGroup.objects.create(user=other_user)
        with self.assertRaises(ValidationError):
            job_answer_set.stage_group = stage_group
            job_answer_set.save()


class JobTokenTests(TestCase):
    def test_create(self):
        self.assertEqual(0, len(JobToken.objects.all()))
        JobToken.objects.create(token='secret1')
        self.assertEqual(1, len(JobToken.objects.all()))
        JobToken.objects.create(token='secret2')
        job_tokens = [x.token for x in JobToken.objects.all()]
        self.assertIn('secret1', job_tokens)
        self.assertIn('secret2', job_tokens)
        self.assertEqual(2, len(job_tokens))

    def test_token_must_be_unique(self):
        JobToken.objects.create(token='secret1')
        with self.assertRaises(IntegrityError) as raised_error:
            JobToken.objects.create(token='secret1')
        self.assertIn('unique constraint', str(raised_error.exception).lower())


class DDSUserTests(TestCase):
    def test_create(self):
        self.assertEqual(0, len(DDSUser.objects.all()))
        DDSUser.objects.create(name='John', dds_id='123')
        self.assertEqual(1, len(DDSUser.objects.all()))
        DDSUser.objects.create(name='Dan', dds_id='456')
        self.assertEqual(2, len(DDSUser.objects.all()))
        ddsusers = DDSUser.objects.all()
        names = [ddsuser.name for ddsuser in ddsusers]
        self.assertIn("John", names)
        self.assertIn("Dan", names)
        dds_ids = [ddsuser.dds_id for ddsuser in ddsusers]
        self.assertIn("123", dds_ids)
        self.assertIn("456", dds_ids)

    def test_dds_id_unique(self):
        DDSUser.objects.create(name='John', dds_id='123')
        with self.assertRaises(IntegrityError):
            DDSUser.objects.create(name='Dan', dds_id='123',)


class ShareGroupTests(TestCase):
    def setUp(self):
        self.ddsuser1 = DDSUser.objects.create(name='John', dds_id='123')
        self.ddsuser2 = DDSUser.objects.create(name='Dan', dds_id='456')

    def test_create_and_add_users(self):
        self.assertEqual(0, len(ShareGroup.objects.all()))
        group = ShareGroup.objects.create(name="ExomeSeq data checkers")
        group.users = [self.ddsuser1, self.ddsuser2]
        group.save()
        group = ShareGroup.objects.first()
        self.assertEqual(group.name, "ExomeSeq data checkers")
        group_users = list(group.users.all())
        self.assertEqual(2, len(group_users))
        self.assertIn(self.ddsuser1, group_users)
        self.assertIn(self.ddsuser2, group_users)


class WorkflowMethodsDocumentTests(TestCase):
    def setUp(self):
        workflow = Workflow.objects.create(name='RnaSeq')
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               object_name='#main',
                                                               version='1',
                                                               url=CWL_URL,
                                                               fields=[])

    def test_crud(self):
        WorkflowMethodsDocument.objects.create(workflow_version=self.workflow_version,
                                               content='#Good Stuff\nSome text.')
        self.assertEqual(1, len(WorkflowMethodsDocument.objects.all()))
        methods_document = WorkflowMethodsDocument.objects.first()
        self.assertEqual(methods_document.workflow_version.id, self.workflow_version.id)
        self.assertEqual(methods_document.content, '#Good Stuff\nSome text.')
        methods_document.content = '#NEW CONTENT'
        methods_document.save()
        methods_document = WorkflowMethodsDocument.objects.first()
        self.assertEqual(methods_document.content, '#NEW CONTENT')
        methods_document.delete()
        self.assertEqual(0, len(WorkflowMethodsDocument.objects.all()))

    def test_workflow_version_link(self):
        methods_document = WorkflowMethodsDocument.objects.create(workflow_version=self.workflow_version,
                                                                  content='#Good Stuff\nSome text.')
        self.assertEqual('#Good Stuff\nSome text.', self.workflow_version.methods_document.content)


class EmailTemplateTests(TestCase):

    def test_requires_unique_names(self):
        EmailTemplate.objects.create(name='template1', body_template='Body1', subject_template='Subject1')
        with self.assertRaises(IntegrityError):
            EmailTemplate.objects.create(name='template1', body_template='Body2', subject_template='Subject1')

    def test_validates_required_fields(self):
        template = EmailTemplate.objects.create()
        with self.assertRaises(ValidationError) as val:
            template.clean_fields()
        self.assertIn('name', val.exception.error_dict)
        self.assertIn('body_template', val.exception.error_dict)
        self.assertIn('subject_template', val.exception.error_dict)


class EmailMessageTests(TestCase):

    def test_default_state_new(self):
        message = EmailMessage.objects.create()
        self.assertEqual(message.state, EmailMessage.MESSAGE_STATE_NEW)

    def test_validates_required_fields(self):
        message = EmailMessage.objects.create()
        with self.assertRaises(ValidationError) as val:
            message.clean_fields()
        error_dict = val.exception.error_dict
        self.assertIn('body', error_dict)
        self.assertIn('subject', error_dict)
        self.assertIn('sender_email', error_dict)
        self.assertIn('to_email', error_dict)
        self.assertNotIn('state', error_dict)
        self.assertNotIn('errors', error_dict)

    def test_validates_email_fields(self):
        message = EmailMessage.objects.create(subject='s', body='b', sender_email='f', to_email='t')
        with self.assertRaises(ValidationError) as val:
            message.clean_fields()
        error_dict = val.exception.error_dict
        self.assertIn('Enter a valid email address.', error_dict.get('to_email')[0].message)
        self.assertIn('Enter a valid email address.', error_dict.get('sender_email')[0].message)

    def test_marks_states(self):
        message = EmailMessage.objects.create()
        self.assertEqual(message.state, EmailMessage.MESSAGE_STATE_NEW)
        message.mark_sent()
        self.assertEqual(message.state, EmailMessage.MESSAGE_STATE_SENT)
        message.mark_error('SMTP Error')
        self.assertEqual(message.state, EmailMessage.MESSAGE_STATE_ERROR)
        self.assertEqual(message.errors, 'SMTP Error')


class CloudSettingsTests(TestCase):

    def setUp(self):
        self.create_args = {
            'vm_project': VMProject.objects.create(name='project1')
        }

    def test_unique_names(self):
        self.create_args['name'] = 'cloud1'
        CloudSettings.objects.create(**self.create_args)
        with self.assertRaises(IntegrityError):
            CloudSettings.objects.create(**self.create_args)

    def test_requires_vm_project(self):
        del self.create_args['vm_project']
        with self.assertRaises(IntegrityError) as val:
            CloudSettings.objects.create(**self.create_args)

    def test_validates_fields(self):
        cloud_settings = CloudSettings.objects.create(**self.create_args)
        with self.assertRaises(ValidationError) as val:
            cloud_settings.clean_fields()
        error_dict = val.exception.error_dict
        error_keys = set(error_dict.keys())
        expected_error_keys ={'ssh_key_name',
                              'network_name',}
        self.assertEqual(error_keys, expected_error_keys)

        # name has a default, should not fail validation
        self.assertNotIn('name', error_dict)
        # other keys not required, should not fail validation
        self.assertNotIn('allocate_floating_ips', error_dict)
        self.assertNotIn('floating_ip_pool_name', error_dict)


class VMCommandTests(TestCase):

    def setUp(self):
        self.create_args = {
            'cloud_settings': CloudSettings.objects.create(name='cloud1', vm_project=VMProject.objects.create(name='project1')),
            'job_settings': JobSettings.objects.create(name='somesettings'),
        }

    def test_creates_with_required_fks(self):
        VMCommand.objects.create(**self.create_args)

    def test_requires_cloud_settings(self):
        del self.create_args['cloud_settings']
        with self.assertRaises(IntegrityError) as val:
            VMCommand.objects.create(**self.create_args)

    def test_validates_fields(self):
        vm_command = VMCommand.objects.create(**self.create_args)
        with self.assertRaises(ValidationError) as val:
            vm_command.clean_fields()
        error_dict = val.exception.error_dict
        error_keys = set(error_dict.keys())
        expected_error_keys ={'image_name',
                              'cwl_base_command'}
        self.assertEqual(error_keys, expected_error_keys)

        # other keys not required, should not fail validation
        self.assertNotIn('cwl_pre_process_command', error_dict)
        self.assertNotIn('cwl_post_process_command', error_dict)


class JobSettingsTests(TestCase):
    def test_defaults(self):
        settings = JobSettings.objects.create()
        self.assertEqual(settings.type, JobSettings.VM_TYPE)
        self.assertEqual(settings.name, 'default_settings')

    def test_unique_names(self):
        JobSettings.objects.create(name='settings1')
        with self.assertRaises(IntegrityError):
            JobSettings.objects.create(name='settings1')


class JobQuestionnaireTypeTests(TestCase):
    def test_basic_functionality(self):
        JobQuestionnaireType.objects.create(tag='human')
        qtypes = JobQuestionnaireType.objects.all()
        self.assertIn('human', [qtype.tag for qtype in qtypes])

    def test_tag_field_unique(self):
        JobQuestionnaireType.objects.create(tag='tag1')
        JobQuestionnaireType.objects.create(tag='tag2')
        with self.assertRaises(IntegrityError):
            JobQuestionnaireType.objects.create(tag='tag1')


class JobFlavorTests(TestCase):
    def test_default_cpus(self):
        JobFlavor.objects.create(name='m1.small')
        flavors = JobFlavor.objects.all()
        self.assertEqual(len(flavors), 1)
        self.assertEqual(flavors[0].name, 'm1.small')
        self.assertEqual(flavors[0].cpus, 1)

    def test_cpus(self):
        JobFlavor.objects.create(name='m1.xxlarge', cpus=32)
        flavors = JobFlavor.objects.all()
        self.assertEqual(len(flavors), 1)
        self.assertEqual(flavors[0].name, 'm1.xxlarge')
        self.assertEqual(flavors[0].cpus, 32)


class WorkflowConfigurationTestCase(TestCase):
    def setUp(self):
        self.workflow = Workflow.objects.create(name='exomeseq', tag='exomeseq')
        self.workflow2 = Workflow.objects.create(name='exomeseq2', tag='exomseq2')
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        self.job_flavor = JobFlavor.objects.create(name='flavor1')
        vm_project = VMProject.objects.create(name='project1')
        cloud_settings = CloudSettings.objects.create(vm_project=vm_project)
        self.job_settings = JobSettings.objects.create()
        self.vm_strategy = JobStrategy.objects.create(
            name='default',
            job_settings=self.job_settings,
            job_flavor=self.job_flavor
        )

    def test_workflow_and_tag_unique(self):
        WorkflowConfiguration.objects.create(
            tag='human',
            workflow=self.workflow,
            system_job_order={},
            default_vm_strategy=self.vm_strategy,
            share_group=self.share_group
        )
        WorkflowConfiguration.objects.create(
            tag='rat',
            workflow=self.workflow,
            system_job_order={},
            default_vm_strategy=self.vm_strategy,
            share_group=self.share_group
        )
        WorkflowConfiguration.objects.create(
            tag='human',
            workflow=self.workflow2,
            system_job_order={},
            default_vm_strategy=self.vm_strategy,
            share_group=self.share_group
        )
        with self.assertRaises(IntegrityError):
            WorkflowConfiguration.objects.create(
                tag='human',
                workflow=self.workflow,
                system_job_order={},
                default_vm_strategy=self.vm_strategy,
                share_group=self.share_group
            )
