from data.models import Workflow, WorkflowVersion, JobQuestionnaire, JobFlavor, VMProject, \
    JobSettings, ShareGroup, WorkflowMethodsDocument, JobQuestionnaireType
from cwltool.context import LoadingContext
from cwltool.workflow import default_make_tool
from cwltool.resolver import tool_resolver
from cwltool.load_tool import load_tool
import sys
import requests
import json
from habanero import cn
from jinja2 import Template
from django.template.defaultfilters import slugify
SCHEMA_ORG_CITATION = 'https://schema.org/citation'
HTTPS_DOI_URL = 'https://dx.doi.org/'
import logging
logger = logging.getLogger(__name__)


class BaseCreator(object):
    """
    Base for command with simple logging facility
    """

    def __init__(self, stdout=sys.stdout, stderr=sys.stderr):
        """
        Creates a base command logger  with logging IO streams
        :param stdout: For writing info log messages
        :param stderr: For writing error messages
        """
        self.stdout = stdout
        self.stderr = stderr

    def log_creation(self, created, kind, name, id):
        if created:
            self.stdout.write("{} '{}' created with id {}".format(kind, name, id))
        else:
            self.stderr.write("{} '{}' already exists with id {}".format(kind, name, id))

    def log(self, message):
        self.stdout.write(message)


class CWLDocument(object):
    """
    Simple CWL document parser
    """

    def __init__(self, url):
        """
        Creates a parser for the given URL
        :param url: The URL to a CWL document to be parsed
        """
        self.url = url
        self._parsed = None

    @property
    def parsed(self):
        """
        Lazy property to parse CWL on-demand
        :return: The CWL document, parsed into a dict
        """
        if self._parsed is None:
            context = LoadingContext({"construct_tool_object": default_make_tool,
                                      "resolver": tool_resolver,
                                      "disable_js_validation": True})
            self._parsed = load_tool(self.url + '#main', context)
        return self._parsed

    @property
    def input_fields(self):
        """
        The input fields from the CWL document
        :return: List of input fields from the CWL document
        """
        return self.parsed.inputs_record_schema.get('fields')

    def get(self, key):
        """
        Gets the value of a key in the root of the CWL document
        :param key: The key to get
        :return: value associated with the key in the parsed CWL
        """
        return self.parsed.tool.get(key)

    def extract_tool_hints(self, hint_class_name):
        """
        Retreieve all tool hints that have the specified class name
        :param hint_class_name: str: name of the class to include
        :return: [dict]: list of hints
        """
        hints = []
        self._extract_tool_hints_recursive(hints, self.parsed, hint_class_name)
        return hints

    def _extract_tool_hints_recursive(self, hints, workflow_node, hint_class_name):
        if hasattr(workflow_node, 'steps'):
            for step in workflow_node.steps:
                self._extract_tool_hints_recursive(hints, step.embedded_tool, hint_class_name=hint_class_name)
        else:
            if workflow_node.hints:
                for hint in workflow_node.hints:
                    if hint['class'] == hint_class_name:
                        hints.append(hint)


class MethodsDocumentContents(object):
    def __init__(self, workflow_version_description, software_requirement_hints, jinja_template_url):
        self.workflow_version_description = workflow_version_description
        self.software_requirement_hints = software_requirement_hints
        self.jinja_template_url = jinja_template_url

    def get_content(self):
        template_args = {}
        for hint in self.software_requirement_hints:
            for package in hint['packages']:
                package_name = package['package']
                versions = package['version']
                citation = package[SCHEMA_ORG_CITATION]
                if citation.startswith(HTTPS_DOI_URL):
                    doi_name = citation.replace(HTTPS_DOI_URL, '')
                    apa_citation = cn.content_negotiation(ids=doi_name, format="text", style="apa")
                else:
                    apa_citation = citation
                template_args[package_name] = {'version': versions[-1], 'citation': apa_citation}
        template_args['description'] = self.workflow_version_description
        response = requests.get(self.jinja_template_url)
        response.raise_for_status()
        template = Template(response.text)
        return template.render(**template_args)


class JobQuestionnaireImporter(BaseCreator):
    """
    Creates a JobQuestionnaire model for a WorkflowVersion with the supplied system job order
    """

    def __init__(self,
                 name,
                 description,
                 type_tag,
                 workflow_version,
                 system_job_order_dict,
                 vm_settings_name,
                 job_flavor_name,
                 share_group_name,
                 volume_size_base,
                 volume_size_factor,
                 cwl_document,
                 stdout=sys.stdout,
                 stderr=sys.stderr):
        super(JobQuestionnaireImporter, self).__init__(stdout, stderr)
        self.name = name
        self.description = description
        self.type_tag = type_tag
        self.workflow_version = workflow_version
        self.system_job_order_dict = system_job_order_dict
        self.job_flavor_name = job_flavor_name
        self.vm_settings_name = vm_settings_name
        self.share_group_name = share_group_name
        self.volume_size_base = volume_size_base
        self.volume_size_factor = volume_size_factor
        # django model objects built up
        self.job_flavor = None
        self.job_questionnaire = None
        self.cwl_document = cwl_document

    def _create_models(self):
        # Fail if JobSettings not found
        self.job_settings = JobSettings.objects.get(name=self.vm_settings_name)
        self.log_creation(False, 'JobSettings', self.vm_settings_name, self.job_settings.id)
        # vm flavor
        self.job_flavor, created = JobFlavor.objects.get_or_create(name=self.job_flavor_name)
        self.log_creation(created, 'JobFlavor', self.job_flavor_name, self.job_flavor.id)
        # share group
        self.share_group, created = ShareGroup.objects.get_or_create(name=self.share_group_name)
        self.log_creation(created, 'ShareGroup', self.share_group_name, self.share_group.id)

        # Extract fields that are not system-provided
        user_fields = []
        for input_field in self.cwl_document.input_fields:
            if not input_field.get('name') in self.system_job_order_dict:
                user_fields.append(input_field)

        # get or create type based on tag
        type, _ = JobQuestionnaireType.objects.get_or_create(tag=self.type_tag)

        # Job questionnaire
        self.job_questionnaire, self.created_job_questionnaire = JobQuestionnaire.objects.get_or_create(
            name=self.name,
            description=self.description,
            workflow_version=self.workflow_version,
            system_job_order_json=json.dumps(self.system_job_order_dict),
            user_fields_json=json.dumps(user_fields),
            job_settings=self.job_settings,
            job_flavor=self.job_flavor,
            share_group=self.share_group,
            volume_size_base=self.volume_size_base,
            volume_size_factor=self.volume_size_factor,
            type=type
        )
        self.log_creation(created, 'JobQuestionnaire', self.job_questionnaire.name, self.job_questionnaire.id)

    def run(self):
        self._create_models()

    def cleanup(self):
        self.job_questionnaire.delete()


class WorkflowImporter(BaseCreator):
    """
    Creates Workflow and WorkflowVersion model objects from a CWL document and supplied version number
    """

    def __init__(self,
                 cwl_document,
                 version_number=1,
                 methods_jinja_template_url=None,
                 tag=None,
                 stdout=sys.stdout,
                 stderr=sys.stderr):
        """
        Creates a WorkflowImporter to import the specified CWL and its variables into bespin-api models
        :param cwl_url: The URL to a CWL Workflow to import
        :param version_number: the version number to assign
        :param stdout: For writing info log messages
        :param stderr: For writing error messages
        """
        super(WorkflowImporter, self).__init__(stdout, stderr)
        self.cwl_document = cwl_document
        self.version_number = version_number
        self.methods_jinja_template_url = methods_jinja_template_url
        self.tag = tag
        # django model objects built up
        self.workflow = None
        self.workflow_version = None

    def _create_models(self):
        # Short description used for the Workflow name
        workflow_name = self.cwl_document.get('label')
        # Longer description used in workflow version
        workflow_version_description = self.cwl_document.get('doc')
        if not self.tag:
            self.tag = slugify(workflow_name)
        workflow, created = Workflow.objects.get_or_create(name=workflow_name, tag=self.tag)
        self.log_creation(created, 'Workflow', workflow_name, workflow.id)
        workflow_version, created = WorkflowVersion.objects.get_or_create(
            workflow=workflow,
            url=self.cwl_document.url,
            description=workflow_version_description,
            version=self.version_number,
        )
        software_requirement_hints = self.cwl_document.extract_tool_hints(hint_class_name="SoftwareRequirement")
        methods_document = MethodsDocumentContents(workflow_version_description, software_requirement_hints,
                                                   jinja_template_url=self.methods_jinja_template_url)
        WorkflowMethodsDocument.objects.get_or_create(
            workflow_version=workflow_version,
            content=methods_document.get_content(),
        )
        self.log_creation(created, 'Workflow Version', workflow_version_description, workflow_version.id)
        self.workflow = workflow
        self.workflow_version = workflow_version

    def cleanup(self):
        self.workflow_version.delete()
        self.workflow.delete()

    def run(self):
        # Parse in the workflow file
        self._create_models()


class ImporterException(Exception):
    def __init__(self, message, cause):
        self.message = message
        self.cause = cause


class WorkflowQuestionnaireImporter(object):

    def __init__(self, data):
        self.data = data

    def run(self):
        self._validate_existing_objects()
        self._load()

    def _validate_existing_objects(self):
        vm_settings_name = self.data['vm_settings_name']
        share_group_name = self.data['share_group_name']
        try:
            JobSettings.objects.get(name=vm_settings_name)
        except JobSettings.DoesNotExist as e:
            raise ImporterException('JobSettings with name \'{}\' not found'.format(vm_settings_name), e)
        try:
            ShareGroup.objects.get(name=share_group_name)
        except ShareGroup.DoesNotExist as e:
            raise ImporterException('ShareGroup with name \'{}\' not found'.format(share_group_name), e)

    def _load(self):
        try:
            logger.info('Loading CWL document from %s', self.data.get('cwl_url'))
            cwl_document = CWLDocument(self.data.get('cwl_url'))
        except Exception as e:
            raise ImporterException('Unable to load CWL Document', e)

        try:
            logger.info('Importing Workflow version %s', str(self.data.get('workflow_version_number')))
            wf_importer = WorkflowImporter(
                cwl_document,
                self.data.get('workflow_version_number'),
                self.data.get('methods_template_url'),
                self.data.get('workflow_tag')
            )
            wf_importer.run()
        except Exception as e:
            logger.exception('Unable to import workflow' )
            raise ImporterException('Unable to import workflow', e)

        try:
            logger.info('Importing Job Questionnaire named %s', self.data.get('name'))
            jq_importer = JobQuestionnaireImporter(
                self.data.get('name'),
                self.data.get('description'),
                self.data.get('type_tag'),
                wf_importer.workflow_version,
                self.data.get('system_json'),
                self.data.get('vm_settings_name'),
                self.data.get('vm_flavor_name'),
                self.data.get('share_group_name'),
                self.data.get('volume_size_base'),
                self.data.get('volume_size_factor'),
                cwl_document
            )
            jq_importer.run()
            self.created_jobquestionnaire = jq_importer.created_job_questionnaire
        except Exception as e:
            logger.exception('Unable to import questionnaire' )
            raise ImporterException('Unable to import questionnaire', e)
