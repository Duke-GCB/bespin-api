from rest_framework import viewsets, permissions, status, mixins
from util import get_user_projects, get_user_project, get_user_project_content, get_user_folder_content, \
    get_readme_file_url
from rest_framework.response import Response
from exceptions import DataServiceUnavailable, WrappedDataServiceException, BespinAPIException, JobTokenException
from data.models import *
from django.db import IntegrityError

from data.serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import detail_route, list_route
from lando import LandoJob
from django.db.models import Q
from django.db import transaction
from jobfactory import create_job_factory
from mailer import EmailMessageSender, JobMailer


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


class WorkflowsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Workflow.objects.all()
    serializer_class = WorkflowSerializer


class WorkflowVersionsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowVersion.objects.all()
    serializer_class = WorkflowVersionSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('workflow',)


class WorkflowMethodsDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowMethodsDocument.objects.all()
    serializer_class = WorkflowMethodsDocumentSerializer


class JobsViewSet(mixins.RetrieveModelMixin,
                  mixins.ListModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobSerializer

    def get_queryset(self):
        return Job.objects.filter(user=self.request.user)

    @detail_route(methods=['post'])
    def start(self, request, pk=None):
        LandoJob(pk, request.user).start()
        return self._serialize_job_response(pk)

    @detail_route(methods=['post'])
    def cancel(self, request, pk=None):
        LandoJob(pk, request.user).cancel()
        return self._serialize_job_response(pk)

    @detail_route(methods=['post'])
    def restart(self, request, pk=None):
        LandoJob(pk, request.user).restart()
        return self._serialize_job_response(pk)

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

    @staticmethod
    def _serialize_job_response(pk, job_status=status.HTTP_200_OK):
        job = Job.objects.get(pk=pk)
        serializer = JobSerializer(job)
        return Response(serializer.data, status=job_status)

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()
        # Only delete job if it hasn't been started yet
        if job.state not in [Job.JOB_STATE_NEW, Job.JOB_STATE_AUTHORIZED]:
            raise BespinAPIException(400, 'You may only delete jobs in NEW and AUTHORIZED states.')
        self.perform_destroy(job)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminJobsViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminJobSerializer
    queryset = Job.objects.all()

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
        return DDSJobInputFile.objects.filter(stage_group__user=self.request.user)


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
        return URLJobInputFile.objects.filter(stage_group__user=self.request.user)


class DDSEndpointViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DDSEndpointSerializer
    queryset = DDSEndpoint.objects.all()


class DDSUserCredViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ReadOnlyDDSUserCredSerializer
    queryset = DDSUserCredential.objects.all()


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


class AdminJobErrorViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobError.objects.all()
    serializer_class = JobErrorSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class JobOutputDirViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = JobDDSOutputProject.objects.all()
    serializer_class = JobOutputDirSerializer

    @detail_route(methods=['post'], serializer_class=DDSFileUrlSerializer, url_path='readme-url')
    def readme_url(self, request, pk=None):
        job_output_dir = JobDDSOutputProject.objects.get(pk=pk)
        dds_file_url = get_readme_file_url(job_output_dir)
        serializer = DDSFileUrlSerializer(dds_file_url)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminJobOutputDirViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobDDSOutputProject.objects.all()
    serializer_class = AdminJobOutputDirSerializer


class JobQuestionnaireViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = JobQuestionnaire.objects.all()
    serializer_class = JobQuestionnaireSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('workflow_version',)


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
        job_factory = create_job_factory(job_answer_set)
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
