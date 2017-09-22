from data import api
from django.conf.urls import url, include
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'dds-projects', api.DDSProjectsViewSet, 'dds-projects')
router.register(r'dds-resources', api.DDSResourcesViewSet, 'dds-resources')
router.register(r'workflows', api.WorkflowsViewSet, 'workflow')
router.register(r'workflow-versions', api.WorkflowVersionsViewSet, 'workflowversion')
router.register(r'jobs', api.JobsViewSet, 'job')
router.register(r'job-file-stage-groups', api.JobFileStageGroupViewSet, 'jobfilestagegroup')
router.register(r'dds-job-input-files', api.DDSJobInputFileViewSet, 'ddsjobinputfile')
router.register(r'url-job-input-files', api.URLJobInputFileViewSet, 'urljobinputfile')
router.register(r'dds-endpoints', api.DDSEndpointViewSet, 'ddsendpoint')
router.register(r'dds-user-credentials', api.DDSUserCredViewSet, 'ddsusercredential')
router.register(r'job-errors', api.JobErrorViewSet, 'joberror')
router.register(r'job-output-dirs', api.JobOutputDirViewSet, 'joboutputdir')
router.register(r'job-questionnaires', api.JobQuestionnaireViewSet, 'jobquestionnaire')
router.register(r'job-answer-sets', api.JobAnswerSetViewSet, 'jobanswerset')
router.register(r'share-groups', api.ShareGroupViewSet, 'sharegroup')
router.register(r'workflow-methods-documents', api.WorkflowMethodsDocumentViewSet, 'workflowmethodsdocument')

# Routes that require admin user
router.register(r'admin/jobs', api.AdminJobsViewSet, 'admin_job')
router.register(r'admin/job-tokens', api.AdminJobTokensViewSet, 'admin_jobtoken')
router.register(r'admin/job-file-stage-groups', api.AdminJobFileStageGroupViewSet, 'admin_jobfilestagegroup')
router.register(r'admin/dds-user-credentials', api.AdminDDSUserCredentialsViewSet, 'admin_ddsusercredentials')
router.register(r'admin/job-errors', api.AdminJobErrorViewSet, 'admin_joberror')
router.register(r'admin/job-output-dirs', api.AdminJobOutputDirViewSet, 'admin_joboutputdir')
router.register(r'admin/share-groups', api.AdminShareGroupViewSet, 'admin_sharegroup')
router.register(r'admin/workflow-methods-documents', api.WorkflowMethodsDocumentViewSet,
                'admin_workflowmethodsdocument')

urlpatterns = [
    url(r'^', include(router.urls)),
]

