from data import api as data_api
from bespin_api_v2 import api
from django.conf.urls import url, include
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'workflows', data_api.WorkflowsViewSet, 'v2-workflow')
router.register(r'workflow-versions', api.WorkflowVersionsViewSet, 'v2-workflowversion')
router.register(r'workflow-version-tool-details', data_api.WorkflowVersionToolDetailsViewSet, 'v2-workflowversiontooldetails')
router.register(r'workflow-configurations', api.WorkflowConfigurationViewSet, 'v2-workflowconfigurations')
router.register(r'job-strategies', api.JobStrategyViewSet, 'v2-jobstrategies')
router.register(r'share-groups', api.ShareGroupViewSet, 'v2-sharegroup')
router.register(r'jobs', api.JobsViewSet, 'v2-job')
router.register(r'job-file-stage-groups', data_api.JobFileStageGroupViewSet, 'v2-jobfilestagegroup')
router.register(r'dds-job-input-files', data_api.DDSJobInputFileViewSet, 'v2-ddsjobinputfile')
router.register(r'url-job-input-files', data_api.URLJobInputFileViewSet, 'v2-urljobinputfile')
router.register(r'dds-endpoints', data_api.DDSEndpointViewSet, 'v2-ddsendpoint')
router.register(r'dds-user-credentials', data_api.DDSUserCredViewSet, 'v2-ddsusercredential')

router.register(r'admin/workflows', api.AdminWorkflowViewSet, 'v2-admin_workflow')
router.register(r'admin/workflow-versions', api.AdminWorkflowVersionViewSet, 'v2-admin_workflowversion')
router.register(r'admin/workflow-configurations', api.AdminWorkflowConfigurationViewSet, 'v2-admin_workflowconfiguration')
router.register(r'admin/jobs', api.AdminJobsViewSet, 'v2-admin_job')
router.register(r'admin/job-file-stage-groups', api.AdminJobFileStageGroupViewSet, 'v2-admin_jobfilestagegroup')
router.register(r'admin/dds-user-credentials', api.AdminDDSUserCredentialsViewSet, 'v2-admin_ddsusercredentials')
router.register(r'admin/job-errors', api.AdminJobErrorViewSet, 'v2-admin_joberror')
router.register(r'admin/job-dds-output-projects', api.AdminJobDDSOutputProjectViewSet, 'v2-admin_jobddsoutputproject')
router.register(r'admin/share-groups', api.AdminShareGroupViewSet, 'v2-admin_sharegroup')
router.register(r'admin/workflow-methods-documents', api.WorkflowMethodsDocumentViewSet, 'v2-admin_workflowmethodsdocument')
router.register(r'admin/workflow-version-tool-details', api.AdminWorkflowVersionToolDetailsViewSet, 'v2-workflowversiontooldetails')
router.register(r'admin/email-templates', api.AdminEmailTemplateViewSet, 'v2-admin_emailtemplate')
router.register(r'admin/email-messages', api.AdminEmailMessageViewSet, 'v2-admin_emailmessage')

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'job-templates/init', api.JobTemplateInitView.as_view(), name='v2-jobtemplate_init'),
    url(r'job-templates/validate', api.JobTemplateValidateView.as_view(), name='v2-jobtemplate_validate'),
    url(r'job-templates/create-job', api.JobTemplateCreateJobView.as_view(), name='v2-jobtemplate_createjob'),
]
