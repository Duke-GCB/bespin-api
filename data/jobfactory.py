from data.models import Job, JobDDSOutputProject, DDSJobInputFile, DDSUserCredential
from data.exceptions import JobFactoryException
from django.conf import settings
import json
import math

BYTES_TO_GB_DIVISOR = 1024 * 1024 * 1024


def create_job_factory_for_answer_set(job_answer_set):
    """
    Create JobFactory based on questions and answers referenced by job_answer_set.
    :param user: User: user who's credentials we will use for building the job
    :param job_answer_set: JobAnswerSet: references questions and their answers to use for building a Job.
    :return: JobFactory
    """
    user = job_answer_set.user
    vm_settings = job_answer_set.questionnaire.vm_settings
    workflow_version = job_answer_set.questionnaire.workflow_version
    stage_group = job_answer_set.stage_group
    job_name = job_answer_set.job_name
    vm_flavor = job_answer_set.questionnaire.vm_flavor
    volume_mounts = job_answer_set.questionnaire.volume_mounts
    share_group = job_answer_set.questionnaire.share_group
    fund_code = job_answer_set.fund_code
    system_job_order = json.loads(job_answer_set.questionnaire.system_job_order_json)
    user_job_order = json.loads(job_answer_set.user_job_order_json)
    job_order_data = JobOrderData(job_answer_set.stage_group, system_job_order, user_job_order)
    job_vm_strategy = JobVMStrategy(vm_settings, vm_flavor,
                                    job_answer_set.questionnaire.volume_size_base,
                                    job_answer_set.questionnaire.volume_size_factor,
                                    volume_mounts)
    return JobFactory(user, workflow_version, job_name, fund_code, job_order_data, job_vm_strategy, share_group)


def create_job_factory_for_workflow_configuration(workflow_configuration, user, job_name, fund_code, job_order_data,
                                                  job_vm_strategy=None):
    if not job_vm_strategy:
        job_vm_strategy = workflow_configuration.default_vm_strategy
    return JobFactory(user, workflow_configuration.workflow_version, job_name, fund_code, job_order_data,
                      job_vm_strategy, workflow_configuration.share_group)


def calculate_volume_size(volume_size_base, volume_size_factor, stage_group):
    """
    Calculates the volume size needed based on the job_answer_set questionnaire settings and stage group data.
    :param job_answer_set: JobAnswerSet: contains questionnaire and stage_group used in calculation
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


class JobVMStrategy(object):
    def __init__(self, vm_settings, vm_flavor, volume_size_base, volume_size_factor, volume_mounts):
        self.vm_settings = vm_settings
        self.vm_flavor = vm_flavor
        self.volume_size_base = volume_size_base
        self.volume_size_factor = volume_size_factor
        self.volume_mounts = volume_mounts


class JobOrderData(object):
    def __init__(self, stage_group, system_job_order, user_job_order):
        self.stage_group = stage_group
        self.system_job_order = system_job_order
        self.user_job_order = user_job_order

    def is_valid(self):
        return self.system_job_order and self.user_job_order

    def get_job_order(self):
        # Create the job order to be submitted. Begin with the system info and overlay the user order
        job_order = self.system_job_order.copy()
        job_order.update(self.user_job_order)
        return job_order


class JobFactory(object):
    """
    Creates Job record in the database based on questions their answers.
    """
    def __init__(self, user, workflow_version, job_name, fund_code, job_order_data, job_vm_strategy, share_group):
        self.user = user
        self.workflow_version = workflow_version
        self.job_name = job_name
        self.fund_code = fund_code
        self.job_order_data = job_order_data
        self.job_vm_strategy = job_vm_strategy
        self.share_group = share_group

    def create_job(self):
        """
        Create a job based on the workflow_version, system job order and user job order
        :return: Job: job that was inserted into the database along with it's output project and input files.
        """
        if not self.job_order_data.is_valid():
            raise JobFactoryException('Attempted to create a job without specifying system job order or user job order')

        job_order = self.job_order_data.get_job_order()

        if settings.REQUIRE_JOB_TOKENS:
            job_state = Job.JOB_STATE_NEW
        else:
            job_state = Job.JOB_STATE_AUTHORIZED

        volume_size = calculate_volume_size(
            volume_size_base=self.job_vm_strategy.volume_size_base,
            volume_size_factor=self.job_vm_strategy.volume_size_factor,
            stage_group=self.job_order_data.stage_group)

        job = Job.objects.create(workflow_version=self.workflow_version,
                                 user=self.user,
                                 stage_group=self.job_order_data.stage_group,
                                 name=self.job_name,
                                 vm_settings=self.job_vm_strategy.vm_settings,
                                 job_order=json.dumps(job_order),
                                 volume_size=volume_size,
                                 vm_volume_mounts=self.job_vm_strategy.volume_mounts,
                                 vm_flavor=self.job_vm_strategy.vm_flavor,
                                 share_group=self.share_group,
                                 fund_code=self.fund_code,
                                 state=job_state
        )
        # Create output project
        # just taking the first worker user credential for now(there is only one production DukeDS instance)
        worker_user_credentials = DDSUserCredential.objects.first()
        JobDDSOutputProject.objects.create(job=job, dds_user_credentials=worker_user_credentials)
        return job

