from rest_framework import serializers
from data.models import Workflow, WorkflowVersion, Job, JobInputFile, DDSJobInputFile, \
    DDSEndpoint, DDSUserCredential, JobOutputDir, URLJobInputFile, JobError


class WorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = ('id', 'name', 'versions')


class WorkflowVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowVersion
        fields = ('id', 'workflow', 'object_name', 'created', 'url', 'version')


class JobOutputDirSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOutputDir
        fields = '__all__'


class JobSerializer(serializers.ModelSerializer):
    workflow_version = WorkflowVersionSerializer(read_only=True)
    output_dir = JobOutputDirSerializer(read_only=True)
    class Meta:
        model = Job
        fields = ('id', 'workflow_version', 'user_id', 'created', 'state', 'last_updated',
                  'vm_flavor', 'vm_instance_name', 'workflow_input_json', 'output_dir')


class DDSEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DDSEndpoint
        fields = ('id','name', 'agent_key', 'api_root')


class DDSUserCredSerializer(serializers.ModelSerializer):
    endpoint = DDSEndpointSerializer(read_only=True)
    class Meta:
        model = DDSUserCredential
        fields = ('id', 'user', 'token', 'endpoint')


class DDSJobInputFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DDSJobInputFile
        fields = '__all__'


class URLJobInputFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = URLJobInputFile
        fields = '__all__'


class JobInputFileSerializer(serializers.ModelSerializer):
    dds_files = serializers.SerializerMethodField()
    url_files = serializers.SerializerMethodField()

    # Sort inner dds files by their index so we can keep our arrays in the same order.
    def get_dds_files(self, obj):
        qset = DDSJobInputFile.objects.filter(job_input_file__pk=obj.pk).order_by('index')
        ser = DDSJobInputFileSerializer(qset, many=True, read_only=True)
        return ser.data

    # Sort inner url files by their index so we can keep our arrays in the same order.
    def get_url_files(self, obj):
        qset = URLJobInputFile.objects.filter(job_input_file__pk=obj.pk).order_by('index')
        ser = URLJobInputFileSerializer(qset, many=True, read_only=True)
        return ser.data

    class Meta:
        model = JobInputFile
        fields = ('id', 'job', 'file_type', 'workflow_name', 'dds_files', 'url_files')


class JobErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobError
        fields = '__all__'
