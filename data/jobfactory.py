from data.models import Job, JobOutputDir, DDSJobInputFile, DDSUserCredential
from rest_framework.exceptions import ValidationError
from util import get_file_name
from exceptions import JobFactoryException
import json



def create_job_factory(job_answer_set):
    """
    Create JobFactory based on questions and answers referenced by job_answer_set.
    :param user: User: user who's credentials we will use for building the job
    :param job_answer_set: JobAnswerSet: references questions and their answers to use for building a Job.
    :return: JobFactory
    """
    user = job_answer_set.user
    workflow_version = job_answer_set.questionnaire.workflow_version
    stage_group = job_answer_set.stage_group
    user_job_order_dict = json.loads(job_answer_set.user_job_order_json)
    system_job_order_dict = json.loads(job_answer_set.questionnaire.system_job_order_json)
    job_name = job_answer_set.job_name
    vm_project_name = job_answer_set.questionnaire.vm_project.name
    vm_flavor_name = job_answer_set.questionnaire.vm_flavor.name
    volume_size = job_answer_set.questionnaire.volume_size
    share_group = job_answer_set.questionnaire.share_group
    fund_code = job_answer_set.questionnaire.fund_code

    factory = JobFactory(user, workflow_version, stage_group, user_job_order_dict, system_job_order_dict, job_name, vm_project_name,
                         vm_flavor_name, volume_size, share_group, fund_code)

    return factory


class JobFactory(object):
    """
    Creates Job record in the database based on questions their answers.
    """
    def __init__(self, user, workflow_version, stage_group, user_job_order, system_job_order, job_name, vm_project_name,
                 vm_flavor_name, volume_size, share_group, fund_code):
        """
        Setup factory
        :param user: User: user we are creating this job for and who's credentials we will use
        :param workflow_version: WorkflowVersion: which CWL workflow are we building a job for
        """
        self.workflow_version = workflow_version
        self.user = user
        self.stage_group = stage_group
        self.user_job_order = user_job_order
        self.system_job_order = system_job_order
        self.job_name = job_name
        self.vm_project_name = vm_project_name
        self.vm_flavor_name = vm_flavor_name
        self.volume_size = volume_size
        self.share_group = share_group
        self.fund_code = fund_code

    def create_job(self):
        """
        Create a job based on the workflow_version, system job order and user job order
        :return: Job: job that was inserted into the database along with it's output directory and input files.
        """

        if self.system_job_order is None or self.user_job_order is None:
            raise JobFactoryException('Attempted to create a job without specifying system job order or user job order')

        # Create the job order to be submitted. Begin with the system info and overlay the user order
        job_order = self.system_job_order.copy()
        job_order.update(self.user_job_order)
        job = Job.objects.create(workflow_version=self.workflow_version,
                                 user=self.user,
                                 stage_group=self.stage_group,
                                 name=self.job_name,
                                 vm_project_name=self.vm_project_name,
                                 vm_flavor=self.vm_flavor_name,
                                 job_order=json.dumps(job_order),
                                 volume_size=self.volume_size,
                                 share_group=self.share_group,
                                 fund_code=self.fund_code
        )
        # Create output directory that will contain resulting project
        # just taking the first worker user credential for now(there is only one production DukeDS instance)
        worker_user_credentials = DDSUserCredential.objects.first()
        JobOutputDir.objects.create(job=job, dds_user_credentials=worker_user_credentials)
        return job

