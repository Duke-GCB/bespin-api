from rest_framework import serializers
from data.models import Workflow, WorkflowVersion, Job, DDSJobInputFile, JobFileStageGroup, \
    DDSEndpoint, DDSUserCredential, JobOutputDir, URLJobInputFile, JobError, JobAnswerSet, \
    JobQuestionnaire, VMFlavor, VMProject, JobToken, ShareGroup, DDSUser


class WorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        resource_name = 'workflows'
        fields = ('id', 'name', 'versions')
        read_only_fields = ('versions',)


class WorkflowVersionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.workflow.name

    class Meta:
        model = WorkflowVersion
        resource_name = 'workflow-versions'
        fields = ('id', 'workflow', 'name', 'description', 'object_name', 'created', 'url', 'version')


class JobOutputDirSerializer(serializers.ModelSerializer):
    def validate(self, data):
        request = self.context['request']
        # You must own the job you are attaching this output directory onto
        if data['job'].user != request.user:
            raise serializers.ValidationError("This job belongs to another user.")
        return data

    class Meta:
        model = JobOutputDir
        resource_name = 'job-output-dirs'
        fields = '__all__'


class AdminJobOutputDirSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOutputDir
        resource_name = 'job-output-dirs'
        fields = '__all__'


class JobErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobError
        resource_name = 'job-errors'
        fields = '__all__'


class JobSerializer(serializers.ModelSerializer):
    output_dir = JobOutputDirSerializer(required=False, read_only=True)
    vm_project_name = serializers.CharField(required=False)
    state = serializers.CharField(read_only=True)
    step = serializers.CharField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())
    job_errors = JobErrorSerializer(required=False, read_only=True, many=True)
    class Meta:
        model = Job
        resource_name = 'jobs'
        fields = ('id', 'workflow_version', 'user', 'name', 'created', 'state', 'step', 'last_updated',
                  'vm_flavor', 'vm_instance_name', 'vm_volume_name', 'vm_project_name', 'job_order',
                  'output_dir', 'job_errors', 'stage_group', 'volume_size', 'fund_code')


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    username = serializers.CharField()


class AdminJobSerializer(serializers.ModelSerializer):
    workflow_version = WorkflowVersionSerializer(required=False)
    output_dir = JobOutputDirSerializer(required=False, read_only=True)
    vm_project_name = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    user = UserSerializer(read_only=True)
    class Meta:
        model = Job
        resource_name = 'jobs'
        fields = ('id', 'workflow_version', 'user', 'name', 'created', 'state', 'step', 'last_updated',
                  'vm_flavor', 'vm_instance_name', 'vm_volume_name', 'vm_project_name', 'job_order',
                  'output_dir', 'stage_group', 'volume_size', 'share_group', 'cleanup_vm', 'fund_code')
        read_only_fields = ('share_group',)


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
        fields = ('id', 'user', 'endpoint')


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


class VMFlavorSerializer(serializers.ModelSerializer):

    class Meta:
        model = VMFlavor
        resource_name = 'vm-flavors'
        fields = '__all__'


class VMProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = VMProject
        resource_name = 'vm-projects'
        fields = '__all__'


class JobAnswerSetSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = JobAnswerSet
        resource_name = 'job-answer-sets'
        fields = '__all__'


class JobQuestionnaireSerializer(serializers.ModelSerializer):

    class Meta:
        model = JobQuestionnaire
        resource_name = 'job-questionnaires'
        fields = '__all__'


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


class DDSUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = DDSUser
        resource_name = 'dds-users'
        fields = '__all__'


class ShareGroupSerializer(serializers.ModelSerializer):
    users = DDSUserSerializer(many=True, read_only=True)
    class Meta:
        model = ShareGroup
        resource_name = 'share-groups'
        fields = '__all__'
