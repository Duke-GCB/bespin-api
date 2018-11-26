from data import api as data_api
from bespin_api_v2 import api
from django.conf.urls import url, include
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'workflows', data_api.WorkflowsViewSet, 'v2-workflow')
router.register(r'workflow-versions', api.WorkflowVersionsViewSet, 'v2-workflowversion')
router.register(r'workflow-configurations', api.WorkflowConfigurationViewSet, 'v2-workflowconfigurations')
router.register(r'vm-strategies', api.VMStrategyViewSet, 'v2-vmstrategies')
router.register(r'share-groups', api.ShareGroupViewSet, 'v2-sharegroup')
router.register(r'jobs', data_api.JobsViewSet, 'v2-job')
router.register(r'job-file-stage-groups', data_api.JobFileStageGroupViewSet, 'v2-jobfilestagegroup')
router.register(r'dds-job-input-files', data_api.DDSJobInputFileViewSet, 'v2-ddsjobinputfile')
router.register(r'url-job-input-files', data_api.URLJobInputFileViewSet, 'v2-urljobinputfile')
router.register(r'dds-endpoints', data_api.DDSEndpointViewSet, 'v2-ddsendpoint')
router.register(r'dds-user-credentials', data_api.DDSUserCredViewSet, 'v2-ddsusercredential')

router.register(r'admin/workflows', api.AdminWorkflowViewSet, 'v2-admin_workflow')
router.register(r'admin/workflow-versions', api.AdminWorkflowVersionViewSet, 'v2-admin_workflowversion')
router.register(r'admin/workflow-configurations', api.AdminWorkflowConfigurationViewSet, 'v2-admin_workflowconfiguration')

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'job-templates/init-job-file', api.JobTemplateInitView.as_view(), name='v2-jobtemplate_initjobfile'),
    url(r'job-templates/create-job', api.JobTemplateCreateJobView.as_view(), name='v2-jobtemplate_createjob'),
]
