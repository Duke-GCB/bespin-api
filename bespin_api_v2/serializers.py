import json
from rest_framework import serializers, fields, permissions, viewsets
from django.contrib.auth.models import User
from data.models import Workflow, WorkflowVersion, JobStrategy, WorkflowConfiguration, JobFileStageGroup, \
    ShareGroup, JobFlavor, Job, JobDDSOutputProject, DDSJobInputFile, URLJobInputFile, JobError, DDSUser, \
    WorkflowMethodsDocument, JobSettings, LandoConnection, JobRuntimeOpenStack, JobRuntimeK8s, JobRuntimeStepK8s
from gcb_web_auth.models import DDSEndpoint, DDSUserCredential
from bespin_api_v2.jobtemplate import JobTemplate, WorkflowVersionConfiguration, JobTemplateValidator, \
    REQUIRED_ERROR_MESSAGE, PLACEHOLDER_ERROR_MESSAGE
from data.serializers import JobFileStageGroupSerializer, AdminDDSUserCredSerializer, \
    JobErrorSerializer, AdminJobDDSOutputProjectSerializer, AdminShareGroupSerializer, \
    WorkflowMethodsDocumentSerializer, JobDDSOutputProjectSerializer, UserSerializer
from data.jobusage import JobUsage


class JSONStrField(serializers.Field):
    def to_representation(self, value):
        return json.loads(value)

    def to_internal_value(self, data):
        return json.dumps(data)


class AdminWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        resource_name = 'workflows'
        fields = '__all__'


class AdminWorkflowVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowVersion
        resource_name = 'workflowversions'
        fields = ['id', 'workflow', 'description', 'object_name', 'created', 'version', 'url', 'fields', 'enable_ui']
        read_only_fields = ('enable_ui', )


class WorkflowVersionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    tag = serializers.SerializerMethodField(required=False)

    def get_name(self, obj):
        return obj.workflow.name

    def get_tag(self, obj):
        return "{}/v{}".format(obj.workflow.tag, obj.version)

    class Meta:
        model = WorkflowVersion
        resource_name = 'workflow-versions'
        fields = ('id', 'workflow', 'name', 'description', 'object_name', 'created', 'url', 'version',
                  'methods_document', 'fields', 'tag', 'enable_ui')


class WorkflowConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowConfiguration
        resource_name = 'workflow-configuration'
        fields = '__all__'


class JobFlavorSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobFlavor
        resource_name = 'job-flavors'
        fields = '__all__'


class JobStrategySerializer(serializers.ModelSerializer):
    job_flavor = JobFlavorSerializer(read_only=True)
    class Meta:
        model = JobStrategy
        resource_name = 'job-strategies'
        fields = '__all__'


class JobTemplateMinimalSerializer(serializers.Serializer):
    tag = serializers.CharField()
    name = serializers.CharField(required=False)
    fund_code = serializers.CharField(required=False)
    job_order = serializers.DictField(required=False)

    def create(self, validated_data):
        return JobTemplate(**validated_data)


class JobTemplateValidatingSerializer(JobTemplateMinimalSerializer):
    """
    Adds validation that requires all fields to have valid values including
    checking the contents of the job order dictionary against fields in the database.
    """
    def validate(self, data):
        JobTemplateValidator(data).run()
        return data


class JobTemplateSerializer(JobTemplateValidatingSerializer):
    stage_group = serializers.PrimaryKeyRelatedField(queryset=JobFileStageGroup.objects.all())
    job_strategy = serializers.PrimaryKeyRelatedField(
        queryset=JobStrategy.objects.all(), required=False)
    job = serializers.PrimaryKeyRelatedField(required=False, read_only=True)


class ShareGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareGroup
        resource_name = 'share-group'
        fields = '__all__'


class AdminJobRuntimeOpenStack(serializers.ModelSerializer):
    cwl_base_command = JSONStrField()
    cwl_post_process_command = JSONStrField()
    cwl_pre_process_command = JSONStrField()
    class Meta:
        model = JobRuntimeOpenStack
        resource_name = 'job-runtime-open-stack'
        fields = ('image_name', 'cwl_base_command', 'cwl_post_process_command', 'cwl_pre_process_command')


class AdminJobRuntimeStepK8s(serializers.ModelSerializer):
    job_flavor = JobFlavorSerializer(read_only=True)
    class Meta:
        model = JobRuntimeStepK8s
        resource_name = 'job-runtime-step-k8s'
        fields = '__all__'


class AdminJobRuntimeK8s(serializers.ModelSerializer):
    steps = AdminJobRuntimeStepK8s(many=True)
    class Meta:
        model = JobRuntimeK8s
        resource_name = 'job-runtime-k8s'
        fields = '__all__'


class AdminLandoConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandoConnection
        resource_name = 'lando-connection'
        fields = '__all__'


class AdminJobSettingsSerializer(serializers.ModelSerializer):
    job_runtime_openstack = AdminJobRuntimeOpenStack(read_only=True)
    job_runtime_k8s = AdminJobRuntimeK8s(read_only=True)

    class Meta:
        model = JobSettings
        resource_name = 'job-settings'
        fields = '__all__'


class AdminJobSerializer(serializers.ModelSerializer):
    workflow_version = WorkflowVersionSerializer(required=False)
    output_project = JobDDSOutputProjectSerializer(required=False, read_only=True)
    name = serializers.CharField(required=False)
    user = UserSerializer(read_only=True)
    job_settings = AdminJobSettingsSerializer(read_only=True)
    job_flavor = JobFlavorSerializer(read_only=True)
    class Meta:
        model = Job
        resource_name = 'jobs'
        fields = ('id', 'workflow_version', 'user', 'name', 'created', 'state', 'step', 'last_updated',
                  'job_settings', 'job_flavor', 'vm_instance_name', 'vm_volume_name', 'vm_volume_mounts', 'job_order',
                  'output_project', 'stage_group', 'volume_size', 'share_group', 'cleanup_vm', 'fund_code')
        read_only_fields = ('share_group', 'job_settings',)


class JobUsageSerializer(serializers.Serializer):
    vm_hours = serializers.FloatField()
    cpu_hours = serializers.FloatField()
    class Meta:
        resource_name = 'job-usage'


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
                  'job_settings', 'vm_instance_name', 'vm_volume_name', 'job_order',
                  'output_project', 'job_errors', 'stage_group', 'volume_size', 'fund_code', 'share_group',
                  'run_token', 'usage')
