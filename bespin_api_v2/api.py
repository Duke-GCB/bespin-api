import json
from rest_framework import viewsets, permissions, status, mixins, generics
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from bespin_api_v2.serializers import AdminWorkflowSerializer, AdminWorkflowVersionSerializer, JobStrategySerializer, \
    WorkflowConfigurationSerializer, JobTemplateMinimalSerializer, JobTemplateSerializer, WorkflowVersionSerializer, \
    ShareGroupSerializer, JobTemplateValidatingSerializer, AdminJobSerializer, JobFileStageGroupSerializer, \
    AdminDDSUserCredSerializer, JobErrorSerializer, AdminJobDDSOutputProjectSerializer, AdminShareGroupSerializer, \
    WorkflowMethodsDocumentSerializer, WorkflowVersionToolDetailsSerializer, JobSerializer, \
    AdminEmailMessageSerializer, AdminEmailTemplateSerializer, AdminLandoConnectionSerializer, \
    AdminJobStrategySerializer, AdminJobSettingsSerializer, JobDebugURLSerializer
from gcb_web_auth.models import DDSUserCredential
from data.api import JobsViewSet as V1JobsViewSet, WorkflowVersionSortedListMixin, ExcludeDeprecatedWorkflowsMixin
from data.models import Workflow, WorkflowVersion, JobStrategy, WorkflowConfiguration, JobFileStageGroup, ShareGroup, \
    Job, JobError, JobDDSOutputProject, WorkflowMethodsDocument, WorkflowVersionToolDetails, EmailMessage, \
    EmailTemplate, LandoConnection, JobSettings, JobDebugURL
from data.exceptions import BespinAPIException
from data.mailer import EmailMessageSender, JobMailer
from data.lando import LandoJob
from rest_framework.exceptions import NotFound


class CreateListRetrieveModelViewSet(mixins.CreateModelMixin,
                                     mixins.ListModelMixin,
                                     mixins.RetrieveModelMixin,
                                     viewsets.GenericViewSet):
    pass


class AdminWorkflowViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminWorkflowSerializer
    queryset = Workflow.objects.all()


class AdminWorkflowVersionViewSet(WorkflowVersionSortedListMixin, CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminWorkflowVersionSerializer
    queryset = WorkflowVersion.objects.all()

    def perform_create(self, serializer):
        serializer.save(enable_ui=False)


class AdminWorkflowVersionToolDetailsViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = WorkflowVersionToolDetailsSerializer
    queryset = WorkflowVersionToolDetails.objects.all()


class AdminWorkflowConfigurationViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = WorkflowConfigurationSerializer
    queryset = WorkflowConfiguration.objects.all()


class JobStrategyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobStrategySerializer
    queryset = JobStrategy.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name',)


class WorkflowVersionsViewSet(WorkflowVersionSortedListMixin, ExcludeDeprecatedWorkflowsMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowVersion.objects.all()
    serializer_class = WorkflowVersionSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('workflow', 'workflow__tag', 'workflow__state', 'version',)
    state_filter_field = 'workflow__state'


class WorkflowConfigurationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WorkflowConfigurationSerializer
    queryset = WorkflowConfiguration.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('tag', 'workflow', 'workflow__tag')


class ShareGroupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated, )
    queryset = ShareGroup.objects.all()
    serializer_class = ShareGroupSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name', 'email', )


class JobTemplateInitView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobTemplateMinimalSerializer

    def perform_create(self, serializer):
        job_template = serializer.save()
        job_template.populate_job_order()


class JobTemplateValidateView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobTemplateValidatingSerializer


class JobTemplateCreateJobView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobTemplateSerializer

    def perform_create(self, serializer):
        job_template = serializer.save()
        job_template.create_and_populate_job(self.request.user)


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
        if original_state != new_state and original_state != Job.JOB_STATE_DEBUG_CLEANUP:
            mailer = JobMailer(self.get_object())
            mailer.mail_current_state()


class AdminJobFileStageGroupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = JobFileStageGroupSerializer
    queryset = JobFileStageGroup.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class AdminDDSUserCredentialsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = DDSUserCredential.objects.all()
    serializer_class = AdminDDSUserCredSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('user',)


class AdminJobErrorViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobError.objects.all()
    serializer_class = JobErrorSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('job',)


class AdminJobDDSOutputProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    queryset = JobDDSOutputProject.objects.all()
    serializer_class = AdminJobDDSOutputProjectSerializer


class AdminShareGroupViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminShareGroupSerializer
    queryset = ShareGroup.objects.all()


class WorkflowMethodsDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowMethodsDocument.objects.all()
    serializer_class = WorkflowMethodsDocumentSerializer


class JobsViewSet(V1JobsViewSet):
    serializer_class = JobSerializer

    @detail_route(methods=['post'], url_path='start-debug')
    def start_debug(self, request, pk=None):
        try:
            LandoJob(pk, request.user).start_debug()
            return self._serialize_job_response(pk)
        except Job.DoesNotExist:
            raise NotFound("Job {} not found.".format(pk))

    @detail_route(methods=['post'], url_path='cancel-debug')
    def cancel_debug(self, request, pk=None):
        try:
            LandoJob(pk, request.user).cancel_debug()
            return self._serialize_job_response(pk)
        except Job.DoesNotExist:
            raise NotFound("Job {} not found.".format(pk))


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


class AdminLandoConnectionViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminLandoConnectionSerializer
    queryset = LandoConnection.objects.all()


class AdminJobStrategyViewSet(CreateListRetrieveModelViewSet, mixins.DestroyModelMixin):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminJobStrategySerializer
    queryset = JobStrategy.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name',)


class AdminJobSettingsViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminJobSettingsSerializer
    queryset = JobSettings.objects.all()

class AdminJobDebugURLViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = JobDebugURLSerializer
    queryset = JobDebugURL.objects.all()
