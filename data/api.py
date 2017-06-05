from rest_framework import viewsets, permissions, status
from util import get_user_projects, get_user_project, get_user_project_content, get_user_folder_content
from rest_framework.response import Response
from exceptions import DataServiceUnavailable, WrappedDataServiceException, BespinAPIException
from data.models import Workflow, WorkflowVersion, Job, JobInputFile, DDSJobInputFile, \
    DDSEndpoint, DDSUserCredential, URLJobInputFile, JobError, JobOutputProject

from data.serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import detail_route
from lando import LandoJob
from django.db.models import Q
from django.db import transaction
from jobfactory import create_job_factory


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


class JobsViewSet(viewsets.ModelViewSet):
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

    @staticmethod
    def _serialize_job_response(pk, job_status=status.HTTP_200_OK):
        job = Job.objects.get(pk=pk)
        serializer = JobSerializer(job)
        return Response(serializer.data, status=job_status)


class AdminJobsViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminJobSerializer
    queryset = Job.objects.all()


class DDSJobInputFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DDSJobInputFileSerializer

    def get_queryset(self):
        return DDSJobInputFile.objects.filter(job_input_file__job__user=self.request.user)


class JobInputFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobInputFileSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)

    def get_queryset(self):
        return JobInputFile.objects.filter(job__user=self.request.user)


class AdminJobInputFileViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = JobInputFileSerializer
    queryset = JobInputFile.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class URLJobInputFileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = URLJobInputFileSerializer

    def get_queryset(self):
        return URLJobInputFile.objects.filter(job_input_file__job__user=self.request.user)


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


class AdminJobErrorViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobError.objects.all()
    serializer_class = JobErrorSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class JobOutputProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = JobOutputProject.objects.all()
    serializer_class = JobOutputProjectSerializer


class AdminJobOutputProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobOutputProject.objects.all()
    serializer_class = AdminJobOutputProjectSerializer


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
