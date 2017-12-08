from __future__ import unicode_literals

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import json


class DDSEndpoint(models.Model):
    """
    Stores the agent key for this application
    """
    name = models.CharField(max_length=255, blank=False, unique=True)
    agent_key = models.CharField(max_length=32, blank=False, unique=True)
    api_root = models.URLField()

    def __unicode__(self):
        return '{} - {}'.format(self.name, self.api_root, )


class DDSUserCredential(models.Model):
    """
    DDS Credentials for bespin users
    """
    endpoint = models.ForeignKey(DDSEndpoint, on_delete=models.CASCADE, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
    token = models.CharField(max_length=32, blank=False, unique=True)
    dds_id = models.CharField(max_length=255, blank=False, unique=True, null=False)

    class Meta:
        unique_together = ('endpoint', 'user',)

    def __unicode__(self):
        return '{} - {}'.format(self.endpoint, self.user, )


class DDSUser(models.Model):
    """
    Details about a DukeDS user.
    """
    name = models.CharField(max_length=255, blank=False, null=False,
                            help_text="Name of the user")
    dds_id = models.CharField(max_length=255, blank=False, unique=True, null=False,
                              help_text="Unique ID assigned to the user in DukeDS")

    def __unicode__(self):
        return 'DDSUser {}'.format(self.name, )


class Workflow(models.Model):
    """
    Name of a workflow that will apply some processing to some data.
    """
    name = models.CharField(max_length=255, blank=False)

    def __unicode__(self):
        return self.name


class WorkflowVersion(models.Model):
    """
    Specific version of a Workflow.
    """
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='versions')
    description = models.TextField()
    object_name = models.CharField(max_length=255, null=True, default='#main',
                                   help_text="Name of the object in a packed workflow to run. "
                                             "Typically set to '#main'.")
    created = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    version = models.IntegerField(null=False)
    url = models.URLField(null=False, help_text="URL to packed CWL workflow file.")

    class Meta:
        ordering = ['version']
        unique_together = ('workflow', 'version',)

    def __unicode__(self):
        return '{} version: {} created: {}'.format(self.workflow.name, self.version, self.created)


class WorkflowMethodsDocument(models.Model):
    """
    Methods document for a particular workflow version.
    """
    workflow_version = models.OneToOneField(WorkflowVersion, on_delete=models.CASCADE, null=False,
                                            related_name='methods_document')
    content = models.TextField(blank=False, null=False, help_text="Methods document contents in markdown.")


class JobFileStageGroup(models.Model):
    """
    Group of files to stage for a job
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL)


class JobToken(models.Model):
    """
    Tokens that give users permission to start a job.
    """
    token = models.CharField(max_length=255, blank=False, null=False, unique=True)

    def __unicode__(self):
        return 'Job Token "{}"'.format(self.token)


class ShareGroup(models.Model):
    """A
    Group of users who will have data shared with them when a job finishes
    """
    name = models.CharField(max_length=255, blank=False, null=False,
                            help_text="Name of this group")
    users = models.ManyToManyField(DDSUser, help_text="Users that belong to this group")
    email = models.EmailField(null=True, help_text="Contact email for this group")

    def __unicode__(self):
        return 'Share Group: {}'.format(self.name)


class VMFlavor(models.Model):
    """
    Specifies parameters for requesting cloud resources
    """
    name = models.CharField(max_length=255, blank=False, unique=True,
                            help_text="The name of the flavor to use when launching instances (specifies CPU/RAM)")

    def __unicode__(self):
        return 'Flavor: {}'.format(self.name)


class VMProject(models.Model):

    name = models.CharField(max_length=255, blank=False, null=False, unique=True,
                            help_text="The name of the project in which to launch instances")

    def __unicode__(self):
        return 'VM Project: {}'.format(self.name)


class CloudSettings(models.Model):
    name = models.CharField(max_length=255, help_text='Short name of this cloudsettings', default='default_settings', unique=True)
    vm_project = models.ForeignKey(VMProject, null=False,
                                   help_text='Project name to use when creating VM instances for this questionnaire')
    ssh_key_name = models.CharField(max_length=255, help_text='Name of SSH key to inject into VM on launch')
    network_name = models.CharField(max_length=255, help_text='Name of network to attach VM to on launch')
    allocate_floating_ips = models.BooleanField(blank=False, default=False,
                                                help_text='Allocate floating IPs to launched VMs')
    floating_ip_pool_name = models.CharField(max_length=255, blank=True, null=True,
                                             help_text='Name of floating IP pool to allocate from')

class VMSettings(models.Model):
    """
    A collection of settings that specify details for VMs launched
    """
    name = models.CharField(max_length=255, help_text='Short name of these settings', default='default_settings', unique=True)
    cloud_settings = models.ForeignKey(CloudSettings, help_text='Cloud settings ')
    image_name = models.CharField(max_length=255, help_text='Name of the VM Image to launch')
    cwl_base_command = models.TextField(help_text='JSON-encoded command array to run the  image\'s installed CWL engine')
    cwl_post_process_command = models.TextField(null=True, blank=True,
                                                help_text='JSON-encoded command array to run after workflow completes')
    cwl_pre_process_command = models.TextField(null=True, blank=True,
                                                help_text='JSON-encoded command array to run before cwl_base_command')

    def __unicode__(self):
        return '{}: {}, Flavor: {}, Proj:{}, Img: {}'.format(self.name, self.pk, self.vm_flavor.name,
                                                             self.vm_project.name, self.image_name)

    class Meta:
        verbose_name_plural = "VM Settings Collections"


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
    JOB_STEP_STORE_OUTPUT = 'O'
    JOB_STEP_TERMINATE_VM = 'T'
    JOB_STEPS = (
        (JOB_STEP_CREATE_VM, 'Create VM'),
        (JOB_STEP_STAGING, 'Staging In'),
        (JOB_STEP_RUNNING, 'Running Workflow'),
        (JOB_STEP_STORE_OUTPUT, 'Store Job Output'),
        (JOB_STEP_TERMINATE_VM, 'Terminate VM'),
    )

    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    name = models.CharField(max_length=255, blank=False, null=False,
                                        help_text="User specified name for this job.")
    fund_code = models.CharField(max_length=255, blank=True, null=True,
                                 help_text="Fund code this job will be charged to.")
    created = models.DateTimeField(auto_now_add=True, blank=False)
    state = models.CharField(max_length=1, choices=JOB_STATES, default='N',
                             help_text="High level state of the project")
    step = models.CharField(max_length=1, choices=JOB_STEPS, null=True, blank=True,
                            help_text="Job step (progress within Running state)")
    last_updated = models.DateTimeField(auto_now=True, blank=False)
    vm_settings = models.ForeignKey(VMSettings, null=False, blank=False,
                                    help_text='Collection of settings to use when launching VM for this job')
    vm_flavor = models.ForeignKey(VMFlavor, null=False,
                                  help_text='VM Flavor to use when creating VM instances for this questionnaire')
    vm_instance_name = models.CharField(max_length=255, blank=True, null=True,
                                        help_text="Name of the vm this job is/was running on.")
    vm_volume_name = models.CharField(max_length=255, blank=True, null=True,
                                      help_text="Name of the volume attached to store data for this job.")
    job_order = models.TextField(null=True,
                                 help_text="CWL input json for use with the workflow.")
    stage_group = models.OneToOneField(JobFileStageGroup, null=True,
                                       help_text='Group of files to stage when running this job')
    run_token = models.OneToOneField(JobToken, null=True, blank=True,
                                     help_text='Token that allows permission for a job to be run')
    volume_size = models.IntegerField(null=False, blank=False, default=100,
                                      help_text='Size in GB of volume created for running this job')
    share_group = models.ForeignKey(ShareGroup, blank=False, null=False,
                                    help_text='Users who will have job output shared with them')
    cleanup_vm = models.BooleanField(default=True, blank=False, null=False,
                                     help_text='Should the VM and Volume be deleted upon job completion')

    def save(self, *args, **kwargs):
        if self.stage_group is not None and self.stage_group.user != self.user:
            raise ValidationError('stage group user does not match job user')
        super(Job, self).save(*args, **kwargs)

    def mark_deleted(self):
        self.state = Job.JOB_STATE_DELETED
        self.save()

    class Meta:
        ordering = ['created']

    def __unicode__(self):
        workflow_name = ''
        if self.workflow_version:
            workflow_name = self.workflow_version.workflow
        return '{} ({}) for user {}'.format(workflow_name, self.get_state_display(), self.user)


class JobDDSOutputProject(models.Model):
    """
    Output project where results of workflow will be uploaded to.
    """
    job = models.OneToOneField(Job, on_delete=models.CASCADE, null=False, related_name='output_project')
    project_id = models.CharField(max_length=255, blank=False, null=True)
    dds_user_credentials = models.ForeignKey(DDSUserCredential, on_delete=models.CASCADE, null=True)
    readme_file_id = models.CharField(max_length=255, blank=False, null=True)

    def __unicode__(self):
        return 'Project: {}'.format(self.project_id)


class JobError(models.Model):
    """
    Record of a particular error that happened with a job including the state the job was at when the error happened.
    """
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=False, related_name='job_errors')
    content = models.TextField(null=False)
    job_step = models.CharField(max_length=1, choices=Job.JOB_STEPS)
    created = models.DateTimeField(auto_now_add=True, blank=False)


class LandoConnection(models.Model):
    """
    Settings used to connect with lando to start, restart or cancel a job.
    """
    host = models.CharField(max_length=255, blank=False, null=False)
    username = models.CharField(max_length=255, blank=False, null=False)
    password = models.CharField(max_length=255, blank=False, null=False)
    queue_name = models.CharField(max_length=255, blank=False, null=False)

    def __unicode__(self):
        return '{} on {}'.format(self.username, self.host)


class JobQuestionnaire(models.Model):
    """
    Specifies a Workflow Version and a set of system-provided answers in JSON format
    """
    name = models.CharField(max_length=255, blank=False, null=False,
                            help_text="Short user facing name")
    description = models.TextField(blank=False, null=False,
                                   help_text="Detailed user facing description")
    workflow_version = models.ForeignKey(WorkflowVersion, on_delete=models.CASCADE, blank=False, null=False,
                                         help_text="Workflow that this questionaire is for")
    system_job_order_json = models.TextField(null=True,
                                             help_text="JSON containing the portion of the job order specified by system.")
    user_fields_json = models.TextField(null=True,
                                        help_text="JSON containing the array of fields required by the user when providing "
                                                  "a job answer set.")
    share_group = models.ForeignKey(ShareGroup, blank=False, null=False,
                                    help_text='Users who will have job output shared with them')
    vm_settings = models.ForeignKey(VMSettings, blank=False, null=False,
                                    help_text='Collection of settings to use when launching job VMs for this questionnaire')
    vm_flavor = models.ForeignKey(VMFlavor, null=False,
                                  help_text='VM Flavor to use when creating VM instances for this questionnaire')
    volume_size_base = models.IntegerField(null=False, blank=False, default=100,
                                           help_text='Base size in GB of for determining job volume size')
    volume_size_factor = models.IntegerField(null=False, blank=False, default=0,
                                             help_text='Number multiplied by total staged data size for '
                                                       'determining job volume size')
    volume_mounts = models.TextField(null=False, blank=False, default=json.dumps({'/dev/vdb1': '/work'}),
                                     help_text='JSON-encoded list of volume mounts, e.g. {"/dev/vdb1": "/work"}')

    def __unicode__(self):
        return '{} desc:{}'.format(self.id, self.description)



class JobAnswerSet(models.Model):
    """
    List of user supplied JobAnswers to JobQuestions.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False,
                             help_text='User who owns this answer set')
    questionnaire = models.ForeignKey(JobQuestionnaire, on_delete=models.CASCADE, null=False,
                                      help_text='determines which questions are appropriate for this answer set')
    job_name = models.CharField(null=False, blank=False, max_length=255,
                                help_text='Name of the job')
    user_job_order_json = models.TextField(null=True, default=json.dumps({}),
                                           help_text="JSON containing the portion of the job order specified by user")
    stage_group = models.OneToOneField(JobFileStageGroup, null=True,
                                       help_text='Collection of files that must be staged for a job to be run')
    fund_code = models.CharField(max_length=255, blank=True, null=True,
                                 help_text="Fund code this job will be charged to.")

    def __unicode__(self):
        return '{} questionnaire:{}'.format(self.id, self.questionnaire.description)

    def save(self, *args, **kwargs):
        if self.stage_group is not None and self.stage_group.user != self.user:
            raise ValidationError('stage group user does not match answer set user')
        super(JobAnswerSet, self).save(*args, **kwargs)


class DDSJobInputFile(models.Model):
    """
    Settings for a file specified in a JobAnswerSet that must be downloaded from DDS before using in a workflow
    """
    stage_group = models.ForeignKey(JobFileStageGroup,
                                    help_text='Stage group to which this file belongs',
                                    related_name='dds_files')
    project_id = models.CharField(max_length=255, blank=False, null=True)
    file_id = models.CharField(max_length=255, blank=False, null=True)
    dds_user_credentials = models.ForeignKey(DDSUserCredential, on_delete=models.CASCADE)
    destination_path = models.CharField(max_length=255, blank=False, null=True)
    size = models.BigIntegerField(null=False, blank=False, default=0, help_text='Size of file in bytes')

    def __unicode__(self):
        return 'DDS Job Input File "{}" id:{}'.format(self.destination_path, self.file_id)


class URLJobInputFile(models.Model):
    """
    Settings for a file specified in a JobAnswerSet that must be downloaded from a URL before using in a workflow
    """
    stage_group = models.ForeignKey(JobFileStageGroup,
                                    help_text='Stage group to which this file belongs',
                                    related_name='url_files')
    url = models.URLField(null=True)
    destination_path = models.CharField(max_length=255, blank=False, null=True)
    size = models.BigIntegerField(null=False, blank=False, default=0, help_text='Size of file in bytes')

    def __unicode__(self):
        return 'URL Job Input File "{}"'.format(self.url)


class EmailTemplate(models.Model):
    """
    Represents a base email message that can be sent
    """
    name = models.CharField(unique=True, max_length=255,
                            help_text='Short name of the template')
    body_template = models.TextField(help_text='Template text for the message body')
    subject_template = models.TextField(help_text='Template text for the message subject')

    def __str__(self):
        return 'Email Template <{}>, subject: {}'.format(
            self.name,
            self.subject_template,
        )


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
    bcc_email = models.TextField(null=True, blank=True, help_text='space-separated Email addresses to bcc')
    state = models.TextField(choices=MESSAGE_STATES, default=MESSAGE_STATE_NEW)
    errors = models.TextField(blank=True, null=True)

    def __str__(self):
        return 'Email Message <{}>, state {}, subject: {}'.format(
            self.id,
            self.state,
            self.subject
        )

    def mark_sent(self):
        self.state = self.MESSAGE_STATE_SENT
        self.save()

    def mark_error(self, errors):
        self.state = self.MESSAGE_STATE_ERROR
        self.errors = errors
        self.save()
