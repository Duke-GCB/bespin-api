from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import JSONField
from gcb_web_auth.models import DDSUserCredential, DDSEndpoint
import json
import re

WORKFLOW_VERSION_PART_SORT_DIGITS = 10


class DDSUser(models.Model):
    """
    Details about a DukeDS user.
    """
    name = models.CharField(max_length=255,
                            help_text="Name of the user")
    dds_id = models.CharField(max_length=255, unique=True,
                              help_text="Unique ID assigned to the user in DukeDS")

    def __str__(self):
        return "DDSUser - pk: {} name: '{}', dds_id: '{}'".format(self.pk, self.name, self.dds_id,)


class Workflow(models.Model):
    """
    Name of a workflow that will apply some processing to some data.
    """
    WORKFLOW_STATE_ACTIVE = 'A'
    WORKFLOW_STATE_DEPRECATED = 'D'
    WORKFLOW_STATES = (
        (WORKFLOW_STATE_ACTIVE, 'Active'),
        (WORKFLOW_STATE_DEPRECATED, 'Deprecated'),
    )

    name = models.CharField(max_length=255)
    tag = models.SlugField(help_text="Unique tag to represent this workflow", unique=True)
    state = models.CharField(max_length=1, choices=WORKFLOW_STATES, default=WORKFLOW_STATE_ACTIVE,
                             help_text="State of the workflow")

    def __str__(self):
        return "Workflow - pk: {} name: '{}', state: {}, tag: '{}'".format(self.pk, self.name, self.get_state_display(), self.tag,)


class WorkflowVersion(models.Model):
    """
    Specific version of a Workflow.
    """
    PACKED_TYPE = 'packed'
    ZIPPED_TYPE = 'zipped'
    WORKFLOW_TYPES = [
        (PACKED_TYPE, 'Single-file packed CWL Workflow'),
        (ZIPPED_TYPE, 'Zip archive containing CWL workflow and dependencies'),
    ]
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='versions')
    description = models.TextField()
    type = models.CharField(max_length=255, choices=WORKFLOW_TYPES, default=PACKED_TYPE)
    workflow_path = models.CharField(max_length=255, blank=True,
                                     help_text="Path to the workflow file after extracting the archive "
                                               "(e.g. exomeseq-gatk4-2.0.0/exomeseq-gatk4.cwl) or for packed workflows, "
                                               "the name of the object to run (e.g. '#main')")
    created = models.DateTimeField(auto_now_add=True)
    version = models.CharField(max_length=255)
    version_info_url = models.URLField(help_text="URL to documentation about this workflow version.", null=True)
    url = models.URLField(help_text="URL to workflow file.")
    fields = JSONField(help_text="Array of fields required by this workflow.")
    enable_ui = models.BooleanField(default=True,
                                    help_text="Should this workflow version be enabled in the web portal.")

    class Meta:
        unique_together = ('workflow', 'version',)

    def __str__(self):
        return "WorkflowVersion - pk: {} workflow.pk: {} - {}/{}: {}".format(self.pk, self.workflow.pk,  self.workflow.tag, self.version, self.description)

    @staticmethod
    def sort_workflow_then_version_key(workflow_version):
        parts = [workflow_version.workflow.id]
        for part in re.split("\.|\-", workflow_version.version):
            left_padded_part = part.zfill(WORKFLOW_VERSION_PART_SORT_DIGITS)
            parts.append(left_padded_part)
        return parts


class WorkflowVersionToolDetails(models.Model):
    workflow_version = models.OneToOneField(WorkflowVersion, related_name='tool_details', null=False)
    details = JSONField(help_text='JSON array of tool details and versions')

    def __str__(self):
        return "WorkflowVersionToolDetails - pk: {}, workflow_version: {}".format(self.pk, self.workflow_version)


class WorkflowMethodsDocument(models.Model):
    """
    Methods document for a particular workflow version.
    """
    workflow_version = models.OneToOneField(WorkflowVersion, on_delete=models.CASCADE,
                                            related_name='methods_document')
    content = models.TextField(help_text="Methods document contents in markdown.")

    def __str__(self):
        return "WorkflowMethodsDocument - pk: {} workflow_version.pk".format(self.pk, self.workflow_version.pk,)


class JobFileStageGroup(models.Model):
    """
    Group of files to stage for a job
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    def __str__(self):
        return "JobFileStageGroup - pk: {} user: '{}'".format(self.pk, self.user,)


class JobToken(models.Model):
    """
    Tokens that give users permission to start a job.
    """
    token = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return "JobToken - pk: {} token: '{}'".format(self.pk, self.token,)


class ShareGroup(models.Model):
    """A
    Group of users who will have data shared with them when a job finishes
    """
    name = models.CharField(max_length=255,
                            help_text="Name of this group")
    users = models.ManyToManyField(DDSUser, help_text="Users that belong to this group")
    email = models.EmailField(blank=True, help_text="Contact email for this group")

    def __str__(self):
        return "ShareGroup - pk: {} name: '{}' email: '{}'".format(self.pk, self.name, self.email,)


class JobFlavor(models.Model):
    """
    Specifies CPU/RAM requested of a cloud resource.
    For a VM we use the name field. For K8s container we use cpus and memory.
    The cpus field is also used for the VM job resource utilization calculation.
    For memory field see https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/#meaning-of-memory.
    """
    name = models.CharField(max_length=255, unique=True,
                            help_text="The name of the flavor to use when launching instances (specifies CPU/RAM)")
    cpus = models.IntegerField(default=1,
                               help_text="How many CPUs are assigned to this flavor")
    memory = models.CharField(default='1Gi', max_length=12,
                              help_text="How much memory in k8s units to be use when running a job with this flavor")

    def __str__(self):
        return "JobFlavor - pk: {} name: '{}' cpus: {} memory: {}".format(self.pk, self.name, self.cpus, self.memory, )


class VMProject(models.Model):

    name = models.CharField(max_length=255, unique=True,
                            help_text="The name of the project in which to launch instances")

    def __str__(self):
        return "VMProject - pk: {} name: '{}'".format(self.pk, self.name,)


class CloudSettingsOpenStack(models.Model):
    name = models.CharField(max_length=255, help_text='Short name of this cloudsettings', default='default_settings', unique=True)
    vm_project = models.ForeignKey(VMProject,
                                   help_text='Project name to use when creating VM instances for this questionnaire')
    ssh_key_name = models.CharField(max_length=255, help_text='Name of SSH key to inject into VM on launch')
    network_name = models.CharField(max_length=255, help_text='Name of network to attach VM to on launch')
    allocate_floating_ips = models.BooleanField(default=False,
                                                help_text='Allocate floating IPs to launched VMs')
    floating_ip_pool_name = models.CharField(max_length=255, blank=True,
                                             help_text='Name of floating IP pool to allocate from')

    def __str__(self):
        return "CloudSettings - pk: {} name: '{}'".format(self.pk, self.name,)

    class Meta:
        verbose_name_plural = "Cloud Settings Collections"


class LandoConnection(models.Model):
    """
    Settings used to connect with lando to start, restart or cancel a job.
    """
    VM_TYPE = 'vm'
    K8S_TYPE = 'k8s'
    TYPES = [
        (VM_TYPE, 'OpenStack Cluster Type'),
        (K8S_TYPE, 'K8s Cluster Type'),
    ]
    cluster_type = models.CharField(max_length=255, choices=TYPES, default=VM_TYPE)
    host = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    queue_name = models.CharField(max_length=255)

    @staticmethod
    def get_for_job_id(job_id):
        job = Job.objects.get(pk=job_id)
        return job.job_settings.lando_connection

    def __str__(self):
        return "LandoConnection - pk: {} host: '{}' cluster_type: {}".format(self.pk, self.host, self.cluster_type)


class JobRuntimeOpenStack(models.Model):
    cloud_settings = models.ForeignKey(CloudSettingsOpenStack, help_text='Cloud settings ')
    image_name = models.CharField(max_length=255, help_text='Name of the VM Image to launch')
    cwl_base_command = models.TextField(help_text='JSON-encoded command array to run the  image\'s installed CWL engine')
    cwl_post_process_command = models.TextField(blank=True,
                                                help_text='JSON-encoded command array to run after workflow completes')
    cwl_pre_process_command = models.TextField(blank=True,
                                                help_text='JSON-encoded command array to run before cwl_base_command')
    def __str__(self):
        return "VMCommand - pk: {} image_name: '{}'".format(
            self.pk, self.image_name)


class JobRuntimeStepK8s(models.Model):
    """
    For memory field see https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/#meaning-of-memory.
    """
    STAGE_DATA_STEP = 'stage_data'
    RUN_WORKFLOW_STEP = 'run_workflow'
    ORGANIZE_OUTPUT_STEP = 'organize_output'
    SAVE_OUTPUT_STEP = 'save_output'
    RECORD_OUTPUT_PROJECT = 'record_output_project'
    STEP_TYPES = [
        (STAGE_DATA_STEP, 'Stage Data'),
        (RUN_WORKFLOW_STEP, 'Run Workflow'),
        (ORGANIZE_OUTPUT_STEP, 'Organize Output'),
        (SAVE_OUTPUT_STEP, 'Save Output'),
        (RECORD_OUTPUT_PROJECT, "Record Output Project"),
    ]
    step_type = models.CharField(max_length=255, choices=STEP_TYPES)
    image_name = models.CharField(max_length=255, help_text='Name of the image to run for this step')
    base_command = JSONField(help_text='JSON array with base command to run')
    flavor = models.ForeignKey(JobFlavor, help_text='Cpu/Memory to use when running this step')

    def __str__(self):
        return "K8sStepCommand - pk: {} step_type: '{}' image_name: '{}' base_command: '{}' cpus: {} memory:{}".format(
            self.pk, self.step_type, self.image_name, self.base_command, self.flavor.cpus, self.flavor.memory)


class JobRuntimeK8s(models.Model):
    steps = models.ManyToManyField(JobRuntimeStepK8s, help_text="Steps to be used by this job runtime")

    def __str__(self):
        return "K8sCommandSet - pk: {}".format(self.pk)


class JobSettings(models.Model):
    """
    A collection of settings that specify details for VMs launched
    """
    name = models.CharField(max_length=255, help_text='Short name of these settings', default='default_settings', unique=True)
    lando_connection = models.ForeignKey(LandoConnection, help_text='Lando connection to use for this job settings')
    job_runtime_openstack = models.ForeignKey(JobRuntimeOpenStack, help_text='VM command to use for type vm', null=True, blank=True)
    job_runtime_k8s = models.ForeignKey(JobRuntimeK8s, help_text='K8s command set to use for type k8s', null=True, blank=True)

    def clean(self):
        cluster_type = self.lando_connection.cluster_type
        if cluster_type == LandoConnection.VM_TYPE:
            if self.job_runtime_openstack is None:
                raise ValidationError("job_runtime_openstack must be filled in when using a lando_connection with OpenStack cluster type")
            if self.job_runtime_k8s:
                raise ValidationError("job_runtime_k8s must be null when using a lando_connection with VM cluster type")
        elif cluster_type == LandoConnection.K8S_TYPE:
            if self.job_runtime_k8s is None:
                raise ValidationError("job_runtime_k8s must be filled in when using a lando_connection with k8s cluster type")
            if self.job_runtime_openstack:
                raise ValidationError("job_runtime_openstack must be null when using a lando_connection with k8s cluster type")

    def __str__(self):
        return "JobSettings - pk: {} name: '{}' cluster_type: '{}'".format(self.pk, self.name,
                                                                           self.lando_connection.cluster_type)

    class Meta:
        verbose_name_plural = "Job Settings Collections"


class Job(models.Model):
    """
    Instance of a workflow that is in some state of progress.
    """
    JOB_STATE_NEW = 'N'
    JOB_STATE_AUTHORIZED = 'A'
    JOB_STATE_STARTING = 'S'
    JOB_STATE_RUNNING = 'R'
    JOB_STATE_FINISHED = 'F'
    JOB_STATE_ERROR = 'E'
    JOB_STATE_CANCELING = 'c'
    JOB_STATE_CANCEL = 'C'
    JOB_STATE_RESTARTING = 'r'
    JOB_STATE_DELETED = 'D'
    JOB_STATES = (
        (JOB_STATE_NEW, 'New'),
        (JOB_STATE_AUTHORIZED, 'Authorized'),
        (JOB_STATE_STARTING, 'Starting'),
        (JOB_STATE_RUNNING, 'Running'),
        (JOB_STATE_FINISHED, 'Finished'),
        (JOB_STATE_ERROR, 'Error'),
        (JOB_STATE_CANCELING, 'Canceling'),
        (JOB_STATE_CANCEL, 'Canceled'),
        (JOB_STATE_RESTARTING, 'Restarting'),
        (JOB_STATE_DELETED, 'Deleted'),
    )

    JOB_STEP_CREATE_VM = 'V'
    JOB_STEP_STAGING = 'S'
    JOB_STEP_RUNNING = 'R'
    JOB_STEP_ORGANIZE_OUTPUT_PROJECT = 'o'
    JOB_STEP_STORE_OUTPUT = 'O'
    JOB_STEP_RECORD_OUTPUT_PROJECT = 'P'
    JOB_STEP_TERMINATE_VM = 'T'
    JOB_STEPS = (
        (JOB_STEP_CREATE_VM, 'Create VM'),
        (JOB_STEP_STAGING, 'Staging In'),
        (JOB_STEP_RUNNING, 'Running Workflow'),
        (JOB_STEP_ORGANIZE_OUTPUT_PROJECT, 'Organize Output Project'),
        (JOB_STEP_STORE_OUTPUT, 'Store Job Output'),
        (JOB_STEP_RECORD_OUTPUT_PROJECT, 'Record Output Project'),
        (JOB_STEP_TERMINATE_VM, 'Terminate VM'),
    )

    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    name = models.CharField(max_length=255,
                                        help_text="User specified name for this job.")
    fund_code = models.CharField(max_length=255, blank=True,
                                 help_text="Fund code this job will be charged to.")
    created = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=1, choices=JOB_STATES, default='N',
                             help_text="High level state of the project")
    step = models.CharField(max_length=1, choices=JOB_STEPS, blank=True,
                            help_text="Job step (progress within Running state)")
    last_updated = models.DateTimeField(auto_now=True)
    job_settings = models.ForeignKey(JobSettings,
                                     help_text='Settings to use when running workflows on VMs or k8s Jobs')
    job_flavor = models.ForeignKey(JobFlavor,
                                   help_text='Cpu/Memory to use when running the workflow associated with this job')
    vm_instance_name = models.CharField(max_length=255, blank=True,
                                        help_text="Name of the vm this job is/was running on.")
    vm_volume_name = models.CharField(max_length=255, blank=True,
                                      help_text="Name of the volume attached to store data for this job.")
    job_order = models.TextField(blank=True,
                                 help_text="CWL input json for use with the workflow.")
    stage_group = models.OneToOneField(JobFileStageGroup, null=True,
                                       help_text='Group of files to stage when running this job')
    run_token = models.OneToOneField(JobToken, blank=True, null=True,
                                     help_text='Token that allows permission for a job to be run')
    volume_size = models.IntegerField(default=100,
                                      help_text='Size in GB of volume created for running this job')
    share_group = models.ForeignKey(ShareGroup,
                                    help_text='Users who will have job output shared with them')
    cleanup_vm = models.BooleanField(default=True,
                                     help_text='Should the VM and Volume be deleted upon job completion')
    vm_volume_mounts = models.TextField(default=json.dumps({'/dev/vdb1': '/work'}),
                                        help_text='JSON-encoded dictionary of volume mounts, e.g. {"/dev/vdb1": "/work"}')

    def save(self, *args, **kwargs):
        if self.stage_group is not None and self.stage_group.user != self.user:
            raise ValidationError('stage group user does not match job user')
        super(Job, self).save(*args, **kwargs)
        if self.should_create_activity():
            JobActivity.objects.create(job=self, state=self.state, step=self.step)

    def should_create_activity(self):
        job_activities = JobActivity.objects.filter(job=self).order_by('-created')
        if not job_activities:
            return True
        latest_activity = job_activities.first()
        return latest_activity.state != self.state or latest_activity.step != self.step

    def mark_deleted(self):
        self.state = Job.JOB_STATE_DELETED
        self.save()

    class Meta:
        ordering = ['created']

    def __str__(self):
        return "Job - pk: {} user: '{}' state: '{}' workflow_version.pk: {} ".format(self.pk, self.user, self.get_state_display(), self.workflow_version.pk, )


class JobActivity(models.Model):
    """
    Contains a record for each time a job state/step changes.
    """
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='job_activities')
    created = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=1, choices=Job.JOB_STATES, default='N',
                             help_text="High level state of the project")
    step = models.CharField(max_length=1, choices=Job.JOB_STEPS, blank=True,
                            help_text="Job step (progress within Running state)")

    class Meta:
        verbose_name_plural = "Job Activities"

    def __str__(self):
        return "JobActivity - pk: {} job.pk: {} state: '{}' step: '{}' created: '{}'".format(self.pk, self.job.pk, self.state, self.step, self.created,)


class JobDDSOutputProject(models.Model):
    """
    Output project where results of workflow will be uploaded to.
    """
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='output_project')
    project_id = models.CharField(max_length=255, blank=True)
    dds_user_credentials = models.ForeignKey(DDSUserCredential, on_delete=models.CASCADE, blank=True)
    readme_file_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "JobDDSOutputProject - pk: {} job.pk: {} project_id: '{}'".format(self.pk, self.job.pk, self.project_id,)


class JobError(models.Model):
    """
    Record of a particular error that happened with a job including the state the job was at when the error happened.
    """
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='job_errors')
    content = models.TextField()
    job_step = models.CharField(max_length=1, choices=Job.JOB_STEPS)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "JobError - pk: {} job.pk: {} job_step: '{}'".format(self.pk, self.job.pk, self.get_job_step_display())


class JobQuestionnaireType(models.Model):
    tag = models.SlugField(help_text="Unique tag for specifying a questionnaire for a workflow version", unique=True)

    def __str__(self):
        return "JobQuestionnaireType - pk: {} tag: '{}'".format(self.pk, self.tag,)


class JobQuestionnaire(models.Model):
    """
    Specifies a Workflow Version and a set of system-provided answers in JSON format
    """
    name = models.CharField(max_length=255,
                            help_text="Short user facing name")
    description = models.TextField(help_text="Detailed user facing description")
    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.CASCADE,
                                         help_text="Workflow that this questionaire is for",
                                         related_name='questionnaires')
    system_job_order_json = models.TextField(blank=True,
                                             help_text="JSON containing the portion of the job order specified by system.")
    user_fields_json = models.TextField(blank=True,
                                        help_text="JSON containing the array of fields required by the user when providing "
                                                  "a job answer set.")
    share_group = models.ForeignKey(ShareGroup,
                                    help_text='Users who will have job output shared with them')
    job_settings = models.ForeignKey(JobSettings,
                                     help_text='Settings to use when running workflows on VMs or k8s Jobs')
    job_flavor = models.ForeignKey(JobFlavor,
                                  help_text='Cpu/Memory to use when running the workflow for this questionnaire')
    volume_size_base = models.IntegerField(default=100,
                                           help_text='Base size in GB of for determining job volume size')
    volume_size_factor = models.IntegerField(default=0,
                                             help_text='Number multiplied by total staged data size for '
                                                       'determining job volume size')
    volume_mounts = models.TextField(default=json.dumps({'/dev/vdb1': '/work'}),
                                     help_text='JSON-encoded dictionary of volume mounts, e.g. {"/dev/vdb1": "/work"}')
    type = models.ForeignKey(JobQuestionnaireType, help_text='Type of questionnaire')

    def make_tag(self):
        workflow_tag = self.workflow_version.workflow.tag
        workflow_version_num = self.workflow_version.version
        return '{}/v{}/{}'.format(workflow_tag, workflow_version_num, self.type.tag)

    @staticmethod
    def split_tag_parts(tag):
        """
        Given tag string return tuple of workflow_tag, version_num, questionnaire_type_tag
        :param tag: str: tag to split into parts
        :return: (workflow_tag, version_num, questionnaire_type_tag)
        """
        parts = tag.split("/")
        if len(parts) != 3:
            return None
        workflow_tag, version_num_str, questionnaire_type_tag = parts
        version_num = int(version_num_str.replace("v", ""))
        return workflow_tag, version_num, questionnaire_type_tag

    def __str__(self):
        return "JobQuestionnaire - pk: {} tag: '{}' name: '{}'".format(self.pk, self.make_tag(), self.name, )


class JobAnswerSet(models.Model):
    """
    List of user supplied JobAnswers to JobQuestions.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             help_text='User who owns this answer set')
    questionnaire = models.ForeignKey(JobQuestionnaire, on_delete=models.CASCADE,
                                      help_text='determines which questions are appropriate for this answer set')
    job_name = models.CharField(max_length=255,
                                help_text='Name of the job')
    user_job_order_json = models.TextField(blank=True, default=json.dumps({}),
                                           help_text="JSON containing the portion of the job order specified by user")
    stage_group = models.OneToOneField(JobFileStageGroup, blank=True, null=True,
                                       help_text='Collection of files that must be staged for a job to be run')
    fund_code = models.CharField(max_length=255, blank=True,
                                 help_text="Fund code this job will be charged to.")

    def save(self, *args, **kwargs):
        if self.stage_group is not None and self.stage_group.user != self.user:
            raise ValidationError('stage group user does not match answer set user')
        super(JobAnswerSet, self).save(*args, **kwargs)

    def __str__(self):
        return "JobAnswerSet - pk: {} user: '{}' questionnaire.pk: {}".format(self.pk, self.user, self.questionnaire.pk,)


class DDSJobInputFile(models.Model):
    """
    Settings for a file specified in a JobAnswerSet that must be downloaded from DDS before using in a workflow
    """
    stage_group = models.ForeignKey(JobFileStageGroup,
                                    help_text='Stage group to which this file belongs',
                                    related_name='dds_files')
    project_id = models.CharField(max_length=255)
    file_id = models.CharField(max_length=255)
    dds_user_credentials = models.ForeignKey(DDSUserCredential, on_delete=models.CASCADE)
    destination_path = models.CharField(max_length=255)
    size = models.BigIntegerField(default=0, help_text='Size of file in bytes')
    sequence_group = models.IntegerField(null=True,
                                         help_text='Determines group(questionnaire field) sequence within the job')
    sequence = models.IntegerField(null=True,
                                   help_text='Determines order within the sequence_group')

    class Meta:
        unique_together = ('stage_group', 'sequence_group', 'sequence',)

    def __str__(self):
        return "DDSJobInputFile - pk: {} stage_group.pk: {} destination_path: '{}' size: {}".\
            format(self.pk, self.stage_group.pk, self.destination_path, self.size,)


class URLJobInputFile(models.Model):
    """
    Settings for a file specified in a JobAnswerSet that must be downloaded from a URL before using in a workflow
    """
    stage_group = models.ForeignKey(JobFileStageGroup,
                                    help_text='Stage group to which this file belongs',
                                    related_name='url_files')
    url = models.URLField()
    destination_path = models.CharField(max_length=255)
    size = models.BigIntegerField(default=0, help_text='Size of file in bytes')
    sequence_group = models.IntegerField(null=True,
                                         help_text='Determines group(questionnaire field) sequence within the job')
    sequence = models.IntegerField(null=True,
                                   help_text='Determines order within the sequence_group')

    class Meta:
        unique_together = ('stage_group', 'sequence_group', 'sequence',)

    def __str__(self):
        return "URLJobInputFile - pk {} stage_group.pk: {} url: '{}' destination_path: '{}' size: {}". \
            format(self.pk, self.stage_group.pk, self.url, self.destination_path, self.size, )


class EmailTemplate(models.Model):
    """
    Represents a base email message that can be sent
    """
    name = models.CharField(unique=True, max_length=255,
                            help_text='Short name of the template')
    body_template = models.TextField(help_text='Template text for the message body')
    subject_template = models.TextField(help_text='Template text for the message subject')

    def __str__(self):
        return "EmailTemplate - pk: {} name: '{}'".format(self.pk, self.name)


class EmailMessage(models.Model):
    """
    Emails messages to send
    """
    MESSAGE_STATE_NEW = 'N'
    MESSAGE_STATE_SENT = 'S'
    MESSAGE_STATE_ERROR = 'E'
    MESSAGE_STATES = (
        (MESSAGE_STATE_NEW, 'New'),
        (MESSAGE_STATE_SENT, 'Sent'),
        (MESSAGE_STATE_ERROR, 'Error'),
    )

    body = models.TextField(help_text='Text of the message body')
    subject = models.TextField(help_text='Text of the message subject')
    sender_email = models.EmailField(help_text='Email address of the sender')
    to_email = models.EmailField(help_text='Email address of the recipient')
    bcc_email = models.TextField(blank=True, help_text='space-separated Email addresses to bcc')
    state = models.TextField(choices=MESSAGE_STATES, default=MESSAGE_STATE_NEW)
    errors = models.TextField(blank=True)

    def __str__(self):
        return "EmailMessage - pk: {}: state: '{}' subject: '{}'".format(self.pk, self.get_state_display(), self.subject,)

    def mark_sent(self):
        self.state = self.MESSAGE_STATE_SENT
        self.save()

    def mark_error(self, errors):
        self.state = self.MESSAGE_STATE_ERROR
        self.errors = errors
        self.save()


class JobStrategy(models.Model):
    """
    Specifies a VM strategy used to create a job.
    """
    name = models.CharField(max_length=255, help_text="Short user facing name")
    job_settings = models.ForeignKey(JobSettings,
                                     help_text='Settings to use when running workflows on VMs or k8s Jobs for this questionnaire')
    job_flavor = models.ForeignKey(JobFlavor,
                                  help_text='VM Flavor to use when creating VM instances for this questionnaire')
    volume_size_base = models.IntegerField(default=100,
                                           help_text='Base size in GB of for determining job volume size')
    volume_size_factor = models.IntegerField(default=0,
                                             help_text='Number multiplied by total staged data size for '
                                                       'determining job volume size')
    volume_mounts = models.TextField(default=json.dumps({'/dev/vdb1': '/work'}),
                                     help_text='JSON-encoded dictionary of volume mounts, e.g. {"/dev/vdb1": "/work"}')

    class Meta:
        verbose_name_plural = "Job Strategies"

    def __str__(self):
        return "JobStrategy - pk: {} name: '{}' flavor: '{}' volume_size_base:'{}' volume_size_factor: '{}'".format(
            self.pk, self.name, self.job_flavor.name, self.volume_size_base, self.volume_size_factor)


class WorkflowConfiguration(models.Model):
    """
    Specifies a set of system-provided answers in JSON format
    """
    tag = models.SlugField(help_text="Unique tag to represent this workflow")
    workflow = models.ForeignKey(Workflow)
    system_job_order = JSONField(help_text="Dictionary containing the portion of the job order specified by system.")
    default_job_strategy = models.ForeignKey(JobStrategy,
                                            help_text='VM setup to use for jobs created with this configuration')
    share_group = models.ForeignKey(ShareGroup,
                                    help_text='Users who will have job output shared with them')

    class Meta:
        unique_together = ('workflow', 'tag', )

    def __str__(self):
        return "WorkflowConfiguration - pk: {}".format(self.pk)
