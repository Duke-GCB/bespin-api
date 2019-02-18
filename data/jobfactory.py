from data.models import Job, JobDDSOutputProject, DDSJobInputFile, DDSUserCredential, WorkflowVersion, \
    WorkflowConfiguration
from data.exceptions import JobFactoryException
from django.conf import settings
import json
import math

BYTES_TO_GB_DIVISOR = 1024 * 1024 * 1024


def create_job_factory_for_answer_set(job_answer_set):
    """
    Create JobFactory based on questions and answers referenced by job_answer_set.
    :param job_answer_set: JobAnswerSet: references questions and their answers to use for building a Job.
    :return: JobFactory
    """
    user = job_answer_set.user
    job_settings = job_answer_set.questionnaire.job_settings
    workflow_version = job_answer_set.questionnaire.workflow_version
    stage_group = job_answer_set.stage_group
    job_name = job_answer_set.job_name
    job_flavor = job_answer_set.questionnaire.job_flavor
    volume_mounts = job_answer_set.questionnaire.volume_mounts
    share_group = job_answer_set.questionnaire.share_group
    fund_code = job_answer_set.fund_code
    system_job_order = json.loads(job_answer_set.questionnaire.system_job_order_json)
    user_job_order = json.loads(job_answer_set.user_job_order_json)
    cloud_strategy = CloudStrategy(job_settings, job_flavor,
                                   job_answer_set.questionnaire.volume_size_base,
                                   job_answer_set.questionnaire.volume_size_factor,
                                   volume_mounts)
    return JobFactory(user, workflow_version,
                      job_name, fund_code, job_answer_set.stage_group,
                      system_job_order, user_job_order,
                      cloud_strategy, share_group)



def calculate_volume_size(volume_size_base, volume_size_factor, stage_group):
    """
    Calculates the volume size needed based volume size settings and size of files to be staged.
    :param volume_size_base: int: base volume size
    :param volume_size_factor: int: value multipied by the size of the stage group
    :param stage_group: StageGroup: input files used with a job
    :return: int: size in GB: volume_size_factor * data_size_in_gb + volume_size_base
    """
    base_in_gb = volume_size_base
    factor = volume_size_factor
    data_size_in_gb = calculate_stage_group_size(stage_group)
    return int(math.ceil(base_in_gb + float(factor) * data_size_in_gb))


def calculate_stage_group_size(stage_group):
    """
    Total up the size of the files contained in the passed stage_group
    :param stage_group: JobFileStageGroup that may contain dds_files and/or url_file
    :return: float: size in GB of all files in the stage group
    """
    total_size_in_bytes = 0
    for dds_file in stage_group.dds_files.all():
        total_size_in_bytes += dds_file.size
    for url_file in stage_group.url_files.all():
        total_size_in_bytes += url_file.size
    return float(total_size_in_bytes) / BYTES_TO_GB_DIVISOR


class CloudStrategy(object):
    def __init__(self, job_settings, job_flavor, volume_size_base, volume_size_factor, volume_mounts):
        self.job_settings = job_settings
        self.job_flavor = job_flavor
        self.volume_size_base = volume_size_base
        self.volume_size_factor = volume_size_factor
        self.volume_mounts = volume_mounts


class JobFactory(object):
    """
    Creates Job record in the database based on questions their answers.
    """
    def __init__(self, user, workflow_version, job_name, fund_code, stage_group, system_job_order, user_job_order,
                 cloud_strategy, share_group):
        self.user = user
        self.workflow_version = workflow_version
        self.job_name = job_name
        self.fund_code = fund_code
        self.stage_group = stage_group
        self.system_job_order = system_job_order
        self.user_job_order = user_job_order
        self.cloud_strategy = cloud_strategy
        self.share_group = share_group

    def _get_job_order(self):
        # Create the job order to be submitted. Begin with the system info and overlay the user order
        job_order = self.system_job_order.copy()
        job_order.update(self.user_job_order)
        return job_order

    def create_job(self):
        """
        Create a job based on the workflow_version, system job order and user job order
        :return: Job: job that was inserted into the database along with it's output project and input files.
        """
        job_order = self._get_job_order()
        if settings.REQUIRE_JOB_TOKENS:
            job_state = Job.JOB_STATE_NEW
        else:
            job_state = Job.JOB_STATE_AUTHORIZED

        volume_size = calculate_volume_size(
            volume_size_base=self.cloud_strategy.volume_size_base,
            volume_size_factor=self.cloud_strategy.volume_size_factor,
            stage_group=self.stage_group)

        job = Job.objects.create(workflow_version=self.workflow_version,
                                 user=self.user,
                                 stage_group=self.stage_group,
                                 name=self.job_name,
                                 job_settings=self.cloud_strategy.job_settings,
                                 job_order=json.dumps(job_order),
                                 volume_size=volume_size,
                                 vm_volume_mounts=self.cloud_strategy.volume_mounts,
                                 job_flavor=self.cloud_strategy.job_flavor,
                                 share_group=self.share_group,
                                 fund_code=self.fund_code,
                                 state=job_state)

        # Create output project
        # just taking the first worker user credential for now(there is only one production DukeDS instance)
        worker_user_credentials = DDSUserCredential.objects.first()
        JobDDSOutputProject.objects.create(job=job, dds_user_credentials=worker_user_credentials)
        return job
