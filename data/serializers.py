from rest_framework import serializers
from django.contrib.auth.models import User
from data.models import Workflow, WorkflowVersion, Job, DDSJobInputFile, JobFileStageGroup, \
    DDSEndpoint, DDSUserCredential, JobDDSOutputProject, URLJobInputFile, JobError, JobAnswerSet, \
    JobQuestionnaire, JobFlavor, VMProject, JobToken, ShareGroup, DDSUser, WorkflowMethodsDocument, \
    EmailTemplate, EmailMessage, VMSettings, CloudSettings, JobActivity
from data.jobusage import JobUsage
from rest_framework.authtoken.models import Token


class WorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        resource_name = 'workflows'
        fields = ('id', 'name', 'versions', 'tag')
        read_only_fields = ('versions',)


class WorkflowVersionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.workflow.name

    class Meta:
        model = WorkflowVersion
        resource_name = 'workflow-versions'
        fields = ('id', 'workflow', 'name', 'description', 'object_name', 'created', 'url', 'version',
                  'methods_document', 'fields', 'questionnaires', 'enable_ui', )


class WorkflowMethodsDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowMethodsDocument
        resource_name = 'workflow-methods-documents'
        fields = ('id', 'workflow_version', 'content')


class JobDDSOutputProjectSerializer(serializers.ModelSerializer):
    def validate(self, data):
        request = self.context['request']
        # You must own the job you are attaching this output project onto
        if data['job'].user != request.user:
            raise serializers.ValidationError("This job belongs to another user.")
        return data

    class Meta:
        model = JobDDSOutputProject
        resource_name = 'job-dds-output-projects'
        fields = ('id', 'job', 'project_id', 'dds_user_credentials')


class AdminJobDDSOutputProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDDSOutputProject
        resource_name = 'job-dds-output-projects'
        fields = '__all__'


class JobErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobError
        resource_name = 'job-errors'
        fields = '__all__'


class JobSerializer(serializers.ModelSerializer):
    output_project = JobDDSOutputProjectSerializer(required=False, read_only=True)
    state = serializers.CharField(read_only=True)
    step = serializers.CharField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())
    job_errors = JobErrorSerializer(required=False, read_only=True, many=True)
    run_token = serializers.CharField(required=False, read_only=True, source='run_token.token')
    usage = serializers.SerializerMethodField()

    def get_usage(self, job):
        """
        Return job usage suitable for displaying in a list to compare jobs.
        Since the usage information (vm hours/cpu hours) for running jobs is not comparable against complete jobs
        the usage will be None for jobs in this state.
        :param job: Job
        :return: dict of job usage data or None if in running state
        """
        if job.state == Job.JOB_STATE_RUNNING:
            return None
        else:
            usage = JobUsage(job)
            serializer = JobUsageSerializer(usage)
            return serializer.data

    class Meta:
        model = Job
        resource_name = 'jobs'
        fields = ('id', 'workflow_version', 'user', 'name', 'created', 'state', 'step', 'last_updated',
                  'vm_settings', 'vm_instance_name', 'vm_volume_name', 'job_order',
                  'output_project', 'job_errors', 'stage_group', 'volume_size', 'fund_code', 'share_group',
                  'run_token', 'usage')


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        resource_name = 'users'
        fields = ('id', 'username', 'first_name', 'last_name', 'email',)


class TokenSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='key', read_only=True)

    class Meta:
        model = Token
        resource_name = 'tokens'
        fields = ('id', 'created')
        read_only_fields = ('created', 'user',)


class VMProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = VMProject
        resource_name = 'vm-projects'
        fields = '__all__'


class VMFlavorSerializer(serializers.ModelSerializer):
    """
    Serializes new JobFlavor model into old VMFlavor format to maintain original vm-flavors api
    """
    class Meta:
        model = JobFlavor
        resource_name = 'vm-flavors'
        fields = '__all__'


class AdminCloudSettingsSerializer(serializers.ModelSerializer):
    vm_project = VMProjectSerializer(read_only=True)
    class Meta:
        model = CloudSettings
        resource_name = 'cloud-settings'
        fields = '__all__'


class AdminVMSettingsSerializer(serializers.ModelSerializer):
    cloud_settings = AdminCloudSettingsSerializer(read_only=True)
    class Meta:
        model = VMSettings
        resource_name = 'vm-settings'
        fields = '__all__'


class AdminJobSerializer(serializers.ModelSerializer):
    workflow_version = WorkflowVersionSerializer(required=False)
    output_project = JobDDSOutputProjectSerializer(required=False, read_only=True)
    name = serializers.CharField(required=False)
    user = UserSerializer(read_only=True)
    vm_settings = AdminVMSettingsSerializer(read_only=True)
    vm_flavor = VMFlavorSerializer(read_only=True, source='job_flavor')
    class Meta:
        model = Job
        resource_name = 'jobs'
        fields = ('id', 'workflow_version', 'user', 'name', 'created', 'state', 'step', 'last_updated',
                  'vm_settings', 'vm_flavor', 'vm_instance_name', 'vm_volume_name', 'vm_volume_mounts', 'job_order',
                  'output_project', 'stage_group', 'volume_size', 'share_group', 'cleanup_vm', 'fund_code')
        read_only_fields = ('share_group', 'vm_settings',)


class DDSEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DDSEndpoint
        resource_name = 'dds-endpoints'
        fields = ('id', 'name', 'api_root')


class DDSUserCredSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())
    class Meta:
        model = DDSUserCredential
        resource_name = 'dds-user-credentials'
        fields = ('id', 'user', 'token', 'endpoint')


class ReadOnlyDDSUserCredSerializer(serializers.ModelSerializer):
    """
    Non-Admin users can only see the keys from the available DukeDS credentials(setup by admin).
    They need access to the keys so they can give download permission to the bespin user.
    """
    class Meta:
        model = DDSUserCredential
        resource_name = 'dds-user-credentials'
        fields = ('id', 'user', 'endpoint', 'dds_id')


class BaseJobInputFileSerializer(serializers.ModelSerializer):

    def validate(self, data):
        request = self.context['request']
        # You must own the job-answer-set you are attaching this file onto
        if data['stage_group'].user != request.user:
            raise serializers.ValidationError("This stage group belongs to another user.")
        return data


class DDSJobInputFileSerializer(BaseJobInputFileSerializer):

    class Meta:
        model = DDSJobInputFile
        resource_name = 'dds-job-input-files'
        fields = '__all__'


class URLJobInputFileSerializer(BaseJobInputFileSerializer):

    class Meta:
        model = URLJobInputFile
        resource_name = 'url-job-input-files'
        fields = '__all__'


class JobFileStageGroupSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())
    dds_files = DDSJobInputFileSerializer(many=True, read_only=True)
    url_files = URLJobInputFileSerializer(many=True, read_only=True)

    class Meta:
        model = JobFileStageGroup
        resource_name = 'job-file-stage-groups'
        fields = ('id', 'user', 'dds_files', 'url_files')


class AdminDDSEndpointSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DDSEndpoint
        resource_name = 'dds-endpoints'
        fields = ('id','name', 'agent_key', 'api_root')


class AdminDDSUserCredSerializer(serializers.ModelSerializer):
    endpoint = AdminDDSEndpointSerializer()

    class Meta:
        model = DDSUserCredential
        resource_name = 'dds-user-credentials'
        fields = ('id', 'user', 'token', 'endpoint')


class DDSProjectSerializer(serializers.Serializer):
    """
    Serializer for dds_resources.DDSProject
    """
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()

    class Meta:
        resource_name = 'dds-projects'


class DDSResourceSerializer(serializers.Serializer):
    kind = serializers.CharField()
    id = serializers.UUIDField()
    name = serializers.CharField()
    project = serializers.UUIDField()
    folder = serializers.UUIDField()
    version = serializers.IntegerField()
    version_id = serializers.UUIDField()
    size = serializers.IntegerField()

    class Meta:
        resource_name = 'dds-resources'


class DDSFileUrlSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    http_verb = serializers.CharField()
    host = serializers.CharField()
    url = serializers.CharField()
    http_headers = serializers.CharField()

    class Meta:
        resource_name = 'dds-file-url'


class JobAnswerSetSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = JobAnswerSet
        resource_name = 'job-answer-sets'
        fields = '__all__'


class JobQuestionnaireSerializer(serializers.ModelSerializer):
    tag = serializers.SerializerMethodField()
    vm_flavor = serializers.IntegerField(source='job_flavor_id')

    def get_tag(self, obj):
        return obj.make_tag()

    class Meta:
        model = JobQuestionnaire
        resource_name = 'job-questionnaires'
        fields = ('id', 'name', 'description', 'workflow_version', 'system_job_order_json',
                  'user_fields_json', 'share_group', 'vm_settings', 'vm_flavor',
                  'volume_size_base', 'volume_size_factor', 'volume_mounts',
                  'tag')  # Removed 'type' since it is incompatible with ember data


class AdminJobTokensSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobToken
        resource_name = 'job-tokens'
        fields = ('id', 'token', 'job')
        read_only_fields = ('job',)


class JobTokensSerializer(serializers.ModelSerializer):
    job = JobSerializer()
    class Meta:
        model = JobToken
        resource_name = 'job-tokens'
        fields = ('token', 'job')


class JobUsageSerializer(serializers.Serializer):
    vm_hours = serializers.FloatField()
    cpu_hours = serializers.FloatField()
    class Meta:
        resource_name = 'job-usage'


class DDSUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = DDSUser
        resource_name = 'dds-users'
        fields = '__all__'


class ShareGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareGroup
        resource_name = 'share-groups'
        fields = ('id', 'name', 'email',)


class AdminShareGroupSerializer(serializers.ModelSerializer):
    users = DDSUserSerializer(many=True, read_only=True)
    class Meta:
        model = ShareGroup
        resource_name = 'share-groups'
        fields = '__all__'


class AdminEmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        resource_name = 'email-templates'
        fields = '__all__'


class AdminEmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        resource_name = 'email-messages'
        fields = '__all__'


class JobActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobActivity
        resource_name = 'job-activities'
        fields = '__all__'


class AdminImportWorkflowQuestionnaireSerializer(serializers.Serializer):

    cwl_url = serializers.URLField()
    workflow_version_number = serializers.IntegerField()
    name = serializers.CharField(min_length=1)
    description = serializers.CharField(min_length=1)
    workflow_tag = serializers.CharField()
    type_tag = serializers.CharField(min_length=1)
    methods_template_url = serializers.URLField()
    system_json = serializers.DictField()
    vm_settings_name = serializers.CharField(min_length=1) # must relate to an existing VM Settings
    vm_flavor_name = serializers.CharField(min_length=1)  # must relate to an existing Job Flavor
                                                          # called vm_flavor_name to maintain original api
    share_group_name = serializers.CharField(min_length=1) # must relate to an existing Share Group
    volume_size_base = serializers.IntegerField()
    volume_size_factor = serializers.IntegerField()
