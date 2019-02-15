from django.contrib import admin
from data.models import *


class CreateOnlyWorkflowVersionAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('workflow', 'object_name', 'version', 'url')
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Workflow)
admin.site.register(WorkflowVersion, CreateOnlyWorkflowVersionAdmin)
admin.site.register(Job)
admin.site.register(JobToken)
admin.site.register(JobDDSOutputProject)
admin.site.register(JobFileStageGroup)
admin.site.register(DDSJobInputFile)
admin.site.register(URLJobInputFile)
admin.site.register(JobError)
admin.site.register(LandoConnection)
admin.site.register(JobQuestionnaire)
admin.site.register(JobQuestionnaireType)
admin.site.register(JobAnswerSet)
admin.site.register(VMProject)
admin.site.register(JobFlavor)
admin.site.register(ShareGroup)
admin.site.register(DDSUser)
admin.site.register(WorkflowMethodsDocument)
admin.site.register(EmailTemplate)
admin.site.register(EmailMessage)
admin.site.register(JobSettings)
admin.site.register(CloudSettings)
admin.site.register(JobActivity)
admin.site.register(VMStrategy)
admin.site.register(WorkflowConfiguration)
