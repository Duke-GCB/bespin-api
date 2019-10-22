"""
Handles communication with lando server that spawns VMs and runs jobs.
Also updates job state before sending messages to lando.
"""
from data.models import Job, LandoConnection, JobDebugURL
from lando_messaging.clients import LandoClient
from rest_framework.exceptions import ValidationError
from data.util import has_download_permissions, give_download_permissions
from django.conf import settings

CANNOT_RESTART_JOB_STEP_MSG = "Restart not allowed for jobs at step {}. Please contact {}."


class LandoConfig(object):
    """
    Settings for the AMQP queue we send messages to lando server over.
    """
    def __init__(self, job_id):
        self.work_queue_config = LandoConnection.get_for_job_id(job_id)


class LandoJob(object):
    """
    Sends messages to lando based on a job.
    """
    def __init__(self, job_id, user):
        """
        :param: job_id: int: id of the job we want to start/cancel/etc.
        :param: user: Django User: user who provides DukeDS permissions for start/restart
        """
        self.job_id = job_id
        self.user = user
        self.config = LandoConfig(job_id)

    def start(self):
        """
        Place message in lando's queue to start running a job.
        Sets job state to STARTING.
        The job must be at the NEW state or this will raise ValidationError.
        """
        job = self.get_job()
        if job.state == Job.JOB_STATE_AUTHORIZED:
            job.state = Job.JOB_STATE_STARTING
            job.save()
            self._give_download_permissions(job)
            self._make_client().start_job(self.job_id)
        else:
            error_msg = "Job is not at AUTHORIZED state. Current state: {}.".format(job.get_state_display())
            if job.state == Job.JOB_STATE_NEW:
                error_msg = "Job needs authorization token before it can start."
            raise ValidationError(error_msg)

    def _make_client(self):
        return LandoClient(self.config, self.config.work_queue_config.queue_name)

    def cancel(self):
        """
        Place message in lando's queue to cancel running a job.
        Sets job state to CANCELING.
        """
        job = self.get_job()  # make sure the job exists
        job.state = Job.JOB_STATE_CANCELING
        job.save()
        self._make_client().cancel_job(self.job_id)

    def restart(self):
        """
        Place message in lando's queue to restart a job that had an error or was canceled.
        Sets job state to RESTARTING.
        The job must be at the ERROR or CANCEL state or this will raise ValidationError.
        """
        job = self.get_job()
        if job.state == Job.JOB_STATE_ERROR and job.step == Job.JOB_STEP_RECORD_OUTPUT_PROJECT:
            msg = CANNOT_RESTART_JOB_STEP_MSG.format(job.get_step_display(), settings.DEFAULT_FROM_EMAIL)
            raise ValidationError(msg)
        if job.state == Job.JOB_STATE_ERROR or job.state == Job.JOB_STATE_CANCEL:
            job.state = Job.JOB_STATE_RESTARTING
            job.save()
            self._give_download_permissions(job)
            self._make_client().restart_job(self.job_id)
        else:
            raise ValidationError("Job is not at ERROR or CANCEL state. Current state: {}.".format(job.get_state_display()))

    def get_job(self):
        return Job.objects.get(pk=self.job_id)

    def _give_download_permissions(self, job):
        """
        Give download permissions to the bespin user for the projects that contain input files.
        :param job: Job: job containing files in one or more projects
        """
        unique_project_user_cred = set()
        for dds_file in job.stage_group.dds_files.all():
            unique_project_user_cred.add((dds_file.project_id, dds_file.dds_user_credentials))
        for project_id, dds_user_credential in unique_project_user_cred:
            if not has_download_permissions(dds_user_credential, project_id):
                give_download_permissions(self.user, project_id, dds_user_credential.dds_id)

    def start_debug(self):
        job = self.get_job()
        if job.state != Job.JOB_STATE_ERROR:
            raise ValidationError("A job must be in ERROR state to debug.")
        job.state = Job.JOB_STATE_DEBUG_SETUP
        job.save()
        self._make_client().start_debug(self.job_id)
        # Lando is expected to setup debug services and will set job to Job.JOB_STATE_DEBUG after doing so

    def cancel_debug(self):
        job = self.get_job()
        if job.state not in [Job.JOB_STATE_DEBUG_SETUP, Job.JOB_STATE_DEBUG]:
            raise ValidationError("A job must be in DEBUG or DEBUG_SETUP state to cancel debugging.")
        job.state = Job.JOB_STATE_DEBUG_CLEANUP
        job.save()
        try:
            job.debug_url.delete()
        except JobDebugURL.DoesNotExist:
            pass
        self._make_client().cancel_debug(self.job_id)
