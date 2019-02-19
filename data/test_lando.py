from django.test import TestCase
from data.lando import LandoJob
from data.models import LandoConnection, Workflow, WorkflowVersion, Job, JobFileStageGroup, \
    DDSJobInputFile, DDSEndpoint, DDSUserCredential, ShareGroup, JobFlavor, VMProject, JobSettings, CloudSettings
from data.tests_models import create_vm_job_settings
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError
from unittest.mock import patch, call


class LandoJobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_user')
        endpoint = DDSEndpoint.objects.create(name='app1', agent_key='abc123')
        user_credentials = DDSUserCredential.objects.create(user=self.user, token='abc123', endpoint=endpoint,
                                                            dds_id='5432')
        LandoConnection.objects.create(host='127.0.0.1', username='jpb67', password='secret', queue_name='lando')
        self.workflow = Workflow.objects.create(name='RnaSeq')
        workflow_version = WorkflowVersion.objects.create(workflow=self.workflow,
                                                          object_name='#main',
                                                          version='1',
                                                          url='',
                                                          fields=[])
        self.stage_group = JobFileStageGroup.objects.create(user=self.user)
        self.share_group = ShareGroup.objects.create(name='Results Checkers')
        job_flavor = JobFlavor.objects.create(name='flavor1')
        self.job_settings = create_vm_job_settings()
        self.job = Job.objects.create(workflow_version=workflow_version,
                                      job_order={},
                                      user=self.user,
                                      stage_group=self.stage_group,
                                      share_group=self.share_group,
                                      volume_size=100,
                                      job_settings=self.job_settings,
                                      job_flavor=job_flavor)
        DDSJobInputFile.objects.create(stage_group=self.stage_group,
                                       project_id='1234',
                                       file_id='5321',
                                       dds_user_credentials=user_credentials,
                                       destination_path='sample.fasta')
        DDSJobInputFile.objects.create(stage_group=self.stage_group,
                                       project_id='1235',
                                       file_id='5322',
                                       dds_user_credentials=user_credentials,
                                       destination_path='sample2.fasta')

    @patch('data.lando.LandoJob._make_client')
    @patch('data.lando.give_download_permissions')
    def test_start_job_new_state(self, mock_give_download_permissions, mock_make_client):
        job = LandoJob(self.job.id, self.user)
        with self.assertRaises(ValidationError) as raised_exception:
            job.start()
        self.assertEqual(raised_exception.exception.detail[0], 'Job needs authorization token before it can start.')

    @patch('data.lando.LandoJob._make_client')
    @patch('data.lando.has_download_permissions')
    @patch('data.lando.give_download_permissions')
    def test_start_job(self, mock_give_download_permissions, mock_has_download_permissions, mock_make_client):
        self.job.state = Job.JOB_STATE_AUTHORIZED
        self.job.save()
        mock_has_download_permissions.return_value = False
        job = LandoJob(self.job.id, self.user)
        job.start()
        mock_make_client().start_job.assert_called()
        mock_give_download_permissions.assert_has_calls([
            call(self.user, '1234', '5432'),
            call(self.user, '1235', '5432')
        ], any_order=True)

    @patch('data.lando.LandoJob._make_client')
    @patch('data.lando.has_download_permissions')
    @patch('data.lando.give_download_permissions')
    def test_start_job_already_has_perms(self, mock_give_download_permissions, mock_has_download_permissions,
                                         mock_make_client):
        self.job.state = Job.JOB_STATE_AUTHORIZED
        self.job.save()
        mock_has_download_permissions.return_value = True
        job = LandoJob(self.job.id, self.user)
        job.start()
        mock_make_client().start_job.assert_called()
        self.assertFalse(mock_give_download_permissions.called)

    @patch('data.lando.LandoJob._make_client')
    @patch('data.lando.has_download_permissions')
    @patch('data.lando.give_download_permissions')
    def test_restart_job(self, mock_give_download_permissions, mock_has_download_permissions, mock_make_client):
        self.job.state = Job.JOB_STATE_ERROR
        self.job.step = Job.JOB_STEP_RUNNING
        self.job.save()

        mock_has_download_permissions.return_value = False
        job = LandoJob(self.job.id, self.user)
        job.restart()
        mock_make_client().restart_job.assert_called()
        mock_give_download_permissions.assert_has_calls([
            call(self.user, '1234', '5432'),
            call(self.user, '1235', '5432')
        ], any_order=True)

    def test_restart_job_in_record_output_step(self):
        self.job.state = Job.JOB_STATE_ERROR
        self.job.step = Job.JOB_STEP_RECORD_OUTPUT_PROJECT
        self.job.save()

        job = LandoJob(self.job.id, self.user)
        with self.assertRaises(ValidationError) as raised_error:
            job.restart()
