import json
from rest_framework import viewsets, permissions, status, mixins, generics
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from bespin_api_v2.serializers import AdminWorkflowSerializer, AdminWorkflowVersionSerializer, VMStrategySerializer, \
    WorkflowConfigurationSerializer, JobTemplateMinimalSerializer, JobTemplateSerializer, WorkflowVersionSerializer, \
    ShareGroupSerializer, JobTemplateValidatingSerializer
from data.serializers import JobSerializer
from data.models import Workflow, WorkflowVersion, JobStrategy, WorkflowConfiguration, JobFileStageGroup, ShareGroup
from data.exceptions import BespinAPIException


class CreateListRetrieveModelViewSet(mixins.CreateModelMixin,
                                     mixins.ListModelMixin,
                                     mixins.RetrieveModelMixin,
                                     viewsets.GenericViewSet):
    pass


class AdminWorkflowViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminWorkflowSerializer
    queryset = Workflow.objects.all()


class AdminWorkflowVersionViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = AdminWorkflowVersionSerializer
    queryset = WorkflowVersion.objects.all()

    def perform_create(self, serializer):
        serializer.save(enable_ui=False)


class AdminWorkflowConfigurationViewSet(CreateListRetrieveModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = WorkflowConfigurationSerializer
    queryset = WorkflowConfiguration.objects.all()


class VMStrategyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = VMStrategySerializer
    queryset = JobStrategy.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name',)


class WorkflowVersionsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = WorkflowVersion.objects.order_by('workflow', 'version')
    serializer_class = WorkflowVersionSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('workflow', 'workflow__tag')


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
