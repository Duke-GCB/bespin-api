from rest_framework import viewsets, permissions, status, mixins
from data.util import get_user_projects, get_user_project, get_user_project_content, get_user_folder_content, \
    get_readme_file_url, get_workflow_version_info
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from data.exceptions import DataServiceUnavailable, WrappedDataServiceException, BespinAPIException, JobTokenException
from data.models import *
from django.db import IntegrityError
from data.serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import detail_route, list_route
from data.lando import LandoJob
from django.db.models import Q
from django.db import transaction
from data.jobfactory import create_job_factory_for_answer_set
from data.mailer import EmailMessageSender, JobMailer
from data.importers import WorkflowQuestionnaireImporter, ImporterException
from rest_framework.authtoken.models import Token


class DDSViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)

    def _ds_operation(self, func, *args):
        try:
            return func(*args)
        except WrappedDataServiceException:
            raise # passes along status code, e.g. 404
        except Exception as e:
            raise DataServiceUnavailable(e)


class DDSProjectsViewSet(DDSViewSet):
    """
    Interfaces with DukeDS API to provide project listing and details.
    Though it is not backed by django models, the ReadOnlyModelViewSet base class
    still works well
    """
    serializer_class = DDSProjectSerializer

    def get_queryset(self):
        return self._ds_operation(get_user_projects, self.request.user)

    def get_object(self):
        project_id = self.kwargs.get('pk')
        return self._ds_operation(get_user_project, self.request.user, project_id)


class DDSResourcesViewSet(DDSViewSet):
    """
    Interfaces with DukeDS API to list files and folders using query parameters. To list the root level
    of a project, GET with ?project_id=:project_id, and to list a folder within a project,
    GET with ?folder_id=:folder_id
    """
    serializer_class = DDSResourceSerializer

    def get_queryset(self):
        # check for project id or folder_id
        folder_id = self.request.query_params.get('folder_id', None)
        project_id = self.request.query_params.get('project_id', None)
        if folder_id:
            return self._ds_operation(get_user_folder_content, self.request.user, folder_id)
        elif project_id:
            return self._ds_operation(get_user_project_content, self.request.user, project_id)
        else:
            raise BespinAPIException(400, 'Getting dds-resources requires either a project_id or folder_id query parameter')


class ExcludeDeprecatedWorkflowsMixin(object):
    """
    Mixin to dynamically build a queryset that excludes deprecated workflows from the listing

    If the exclude() filter is always applied to the queryset, then there's no way to list or access deprecated
    workflows through the API. They are simply invisible. Instead, we exclude them from the queryset by default, but
    include them ahead of other filtering or for specific request id.
    """

    state_filter_field = None

    def get_queryset(self):
        """
        Exclude deprecated workflows from queryset, unless request is
        filtering on state or fetching a single workflow by id
        :return: Workflows queryset
        """
        if self.state_filter_field not in self.filter_fields:
            raise(BespinAPIException(500, 'Cannot use ExcludeDeprecatedWorkflowsMixin without setting '
                                          'state_filter_field to one of the filter_fields: {}'
                                     .format(self.state_filter_field)))
        queryset = super(ExcludeDeprecatedWorkflowsMixin, self).get_queryset()
        state_query = self.request.query_params.get(self.state_filter_field, None)
        if state_query is None and self.action == 'list':
            exclude_filter = {self.state_filter_field: Workflow.WORKFLOW_STATE_DEPRECATED}
            queryset = queryset.exclude(**exclude_filter)
        return queryset


class WorkflowsViewSet(ExcludeDeprecatedWorkflowsMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Workflow.objects.all()
    serializer_class = WorkflowSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('tag','state', )
    state_filter_field = 'state'


class WorkflowVersionSortedListMixin(object):
    """
    Overrides list method and returns a list that is sorted using WorkflowVersion.sort_workflow_then_version_key.
    NOTE: This removes DRF pagination support.
    """
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        items = sorted(queryset, key=WorkflowVersion.sort_workflow_then_version_key)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)


class WorkflowVersionsViewSet(WorkflowVersionSortedListMixin, ExcludeDeprecatedWorkflowsMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowVersion.objects.all()
    serializer_class = WorkflowVersionSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('workflow', 'enable_ui', 'workflow__state')
    state_filter_field = 'workflow__state'

    @detail_route(methods=['get'], serializer_class=WorkflowVersionInfoContentsSerializer, url_path='version-info')
    def version_info(self, request, pk=None):
        version = self.get_queryset().get(pk=pk)
        info = get_workflow_version_info(version)
        serializer = self.get_serializer(info)
        return Response(serializer.data)


class WorkflowMethodsDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowMethodsDocument.objects.all()
    serializer_class = WorkflowMethodsDocumentSerializer


class WorkflowVersionToolDetailsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_class = (permissions.IsAuthenticated,)
    queryset = WorkflowVersionToolDetails.objects.all()
    serializer_class = WorkflowVersionToolDetailsSerializer


class JobsViewSet(mixins.RetrieveModelMixin,
                  mixins.ListModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobSerializer

    # If job is in NEW or AUTHORIZED states it can be truly deleted
    DESTROY_ALLOWED_STATES = (Job.JOB_STATE_NEW, Job.JOB_STATE_AUTHORIZED,)
    # If job is in another not-running state, user can mark it deleted
    USER_DELETE_ALLOWED_STATES = (Job.JOB_STATE_CANCEL, Job.JOB_STATE_ERROR, Job.JOB_STATE_FINISHED,)

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user).exclude(state=Job.JOB_STATE_DELETED)

    @detail_route(methods=['post'])
    def start(self, request, pk=None):
        try:
            LandoJob(pk, request.user).start()
            return self._serialize_job_response(pk)
        except Job.DoesNotExist:
            raise NotFound("Job {} not found.".format(pk))

    @detail_route(methods=['post'])
    def cancel(self, request, pk=None):
        try:
            LandoJob(pk, request.user).cancel()
            return self._serialize_job_response(pk)
        except Job.DoesNotExist:
            raise NotFound("Job {} not found.".format(pk))

    @detail_route(methods=['post'])
    def restart(self, request, pk=None):
        try:
            LandoJob(pk, request.user).restart()
            return self._serialize_job_response(pk)
        except Job.DoesNotExist:
            raise NotFound("Job {} not found.".format(pk))

    # Wrapping this in JobTokensSerializer so we can pass in the token inside a job-tokens payload when
    # used with vnd.rootobject+json Content-type. Returns serialized 'job' as part of the response inside the
    # job-tokens payload when used with vnd.rootobject+json Accept.
    @detail_route(methods=['post'], serializer_class=JobTokensSerializer)
    def authorize(self, request, pk=None):
        """
        Authorizes this job for running by supplying a valid job token.
        """
        request_token = request.data.get('token')
        if not request_token:
            raise JobTokenException(detail='Missing required token field.')
        job = Job.objects.get(pk=pk)
        if job.state != Job.JOB_STATE_NEW:
            raise JobTokenException(detail='Job state must be NEW.')
        try:
            job.run_token = JobToken.objects.get(token=request_token)
        except JobToken.DoesNotExist:
            raise JobTokenException(detail='This is not a valid token.')
        job.state = Job.JOB_STATE_AUTHORIZED
        try:
            job.save()
        except IntegrityError:
            raise JobTokenException(detail='This token has already been used.')
        serializer = JobTokensSerializer(job.run_token)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @detail_route(methods=['post'], serializer_class=JobUsageSerializer, url_path='live-usage')
    def live_usage(self, request, pk=None):
        try:
            job = Job.objects.get(pk=pk)
            live_usage = JobUsage(job)
            serializer = JobUsageSerializer(live_usage)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Job.DoesNotExist:
            raise NotFound("Job {} not found.".format(pk))

    @staticmethod
    def _serialize_job_response(pk, job_status=status.HTTP_200_OK):
        job = Job.objects.get(pk=pk)
        serializer = JobSerializer(job)
        return Response(serializer.data, status=job_status)

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()
        if job.state in JobsViewSet.DESTROY_ALLOWED_STATES:
            self.perform_destroy(job)
            return Response(status=status.HTTP_204_NO_CONTENT)
        elif job.state in JobsViewSet.USER_DELETE_ALLOWED_STATES:
            job.mark_deleted()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            raise BespinAPIException(400, 'You may only delete jobs in NEW, AUTHORIZED , CANCEL, ERROR, or FINISHED states.')


class AdminJobsViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminJobSerializer
    queryset = Job.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('vm_instance_name',)

    def perform_update(self, serializer):
        # Overrides perform update to notify about state changes
        # If the job state changed, notify about the state change
        original_state = self.get_object().state
        serializer.save()
        new_state = self.get_object().state
        if original_state != new_state:
            mailer = JobMailer(self.get_object())
            mailer.mail_current_state()


class DDSJobInputFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DDSJobInputFileSerializer

    def get_queryset(self):
        return DDSJobInputFile.objects.filter(stage_group__user=self.request.user).order_by(
            'sequence_group', 'sequence')


class JobFileStageGroupViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobFileStageGroupSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)

    def get_queryset(self):
        return JobFileStageGroup.objects.filter(user=self.request.user)


class AdminJobFileStageGroupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = JobFileStageGroupSerializer
    queryset = JobFileStageGroup.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class URLJobInputFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = URLJobInputFileSerializer

    def get_queryset(self):
        return URLJobInputFile.objects.filter(stage_group__user=self.request.user).order_by(
            'sequence_group', 'sequence')


class DDSEndpointViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DDSEndpointSerializer
    queryset = DDSEndpoint.objects.all()


class DDSUserCredViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ReadOnlyDDSUserCredSerializer
    queryset = DDSUserCredential.objects.all().order_by('id')


class AdminDDSUserCredentialsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = DDSUserCredential.objects.all()
    serializer_class = AdminDDSUserCredSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('user',)


class JobErrorViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobErrorSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)

    def get_queryset(self):
        return JobError.objects.filter(job__user=self.request.user)


class UserViewSet(viewsets.GenericViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer

    @list_route(methods=['get'], url_path='current-user')
    def current_user(self, request):
        current_user = self.request.user
        serializer = UserSerializer(self.request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TokenViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = TokenSerializer

    def get_queryset(self):
        return Token.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if Token.objects.filter(user=request.user).exists():
            message = "Only one token is allowed per user. " \
                      "You must delete your existing token before you can create a new token."
            raise BespinAPIException(status.HTTP_400_BAD_REQUEST, message)
        token = Token.objects.create(user=request.user)
        serializer = TokenSerializer(token)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminJobErrorViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobError.objects.all()
    serializer_class = JobErrorSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class JobDDSOutputProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = JobDDSOutputProject.objects.all()
    serializer_class = JobDDSOutputProjectSerializer

    @detail_route(methods=['post'], serializer_class=DDSFileUrlSerializer, url_path='readme-url')
    def readme_url(self, request, pk=None):
        job_output_project = JobDDSOutputProject.objects.get(pk=pk)
        dds_file_url = get_readme_file_url(job_output_project)
        serializer = DDSFileUrlSerializer(dds_file_url)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminJobDDSOutputProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobDDSOutputProject.objects.all()
    serializer_class = AdminJobDDSOutputProjectSerializer


class JobQuestionnaireViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobQuestionnaireSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('workflow_version',)

    def get_queryset(self):
        tag = self.request.query_params.get('tag', None)
        if tag:
            parts = JobQuestionnaire.split_tag_parts(tag)
            if parts:
                workflow_tag, version_num, questionnaire_type_tag = parts
                return JobQuestionnaire.objects.filter(workflow_version__workflow__tag=workflow_tag,
                                                       workflow_version__version=version_num,
                                                       type__tag=questionnaire_type_tag)
            else:
                return JobQuestionnaire.objects.none()
        else:
            return JobQuestionnaire.objects.all()


class JobAnswerSetViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobAnswerSetSerializer

    def get_queryset(self):
        return JobAnswerSet.objects.filter(user=self.request.user)

    @transaction.atomic
    @detail_route(methods=['post'], serializer_class=JobSerializer, url_path='create-job')
    def create_job(self, request, pk=None):
        """
        Create a new job based on our JobAnswerSet and return its json.
        """
        job_answer_set = JobAnswerSet.objects.filter(user=request.user, pk=pk).first()
        job_factory = create_job_factory_for_answer_set(job_answer_set)
        job = job_factory.create_job()
        serializer = JobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminJobTokensViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminJobTokensSerializer
    queryset = JobToken.objects.all()


class AdminShareGroupViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminShareGroupSerializer
    queryset = ShareGroup.objects.all()


class ShareGroupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ShareGroupSerializer
    queryset = ShareGroup.objects.all()


class AdminEmailMessageViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminEmailMessageSerializer
    queryset = EmailMessage.objects.all()

    @detail_route(methods=['post'], url_path='send')
    def send(self, request, pk=None):
        """
        Send an email message
        """
        message = self.get_object()
        sender = EmailMessageSender(message)
        sender.send()
        serializer = self.get_serializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminEmailTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminEmailTemplateSerializer
    queryset = EmailTemplate.objects.all()


class JobActivityViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobActivitySerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)

    def get_queryset(self):
        return JobActivity.objects.filter(job__user=self.request.user).order_by('job', 'created')


class AdminImportWorkflowQuestionnaireViewSet(mixins.CreateModelMixin,
                                              viewsets.GenericViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminImportWorkflowQuestionnaireSerializer
    queryset = []

    def perform_create(self, serializer):
        importer = WorkflowQuestionnaireImporter(serializer.validated_data)
        try:
            importer.run()
            return importer.created_jobquestionnaire
        except ImporterException as e:
            raise BespinAPIException(status.HTTP_400_BAD_REQUEST, e.message)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if self.perform_create(serializer):
            response_status = status.HTTP_201_CREATED # created new
        else:
            response_status = status.HTTP_200_OK # Already imported
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=response_status, headers=headers)
