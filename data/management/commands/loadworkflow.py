from django.core.management.base import BaseCommand
from argparse import FileType
from data.models import Workflow, WorkflowVersion, JobQuestionnaire, VMFlavor, VMProject, ShareGroup, WorkflowMethodsDocument
from cwltool.load_tool import load_tool
from cwltool.workflow import defaultMakeTool
from _private import BaseCreator
import json
import sys
import requests
from habanero import cn
from jinja2 import Template
SCHEMA_ORG_CITATION = 'https://schema.org/citation'
HTTPS_DOI_URL = 'https://dx.doi.org/'


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
            self._parsed = load_tool(self.url + '#main', defaultMakeTool)
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
    def __init__(self, software_requirement_hints, jinja_template_url):
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
                 workflow_version,
                 system_job_order_file,
                 vm_flavor_name,
                 vm_project_name,
                 share_group_name,
                 volume_size_base,
                 volume_size_factor,
                 stdout=sys.stdout,
                 stderr=sys.stderr):
        super(JobQuestionnaireImporter, self).__init__(stdout, stderr)
        self.name = name
        self.description = description
        self.workflow_version = workflow_version
        self.system_job_order_dict = json.load(system_job_order_file)
        self.vm_flavor_name = vm_flavor_name
        self.vm_project_name = vm_project_name
        self.share_group_name = share_group_name
        self.volume_size_base = volume_size_base
        self.volume_size_factor = volume_size_factor
        # django model objects built up
        self.vm_flavor = None
        self.vm_project = None
        self.job_questionnaire = None

    def _create_models(self):
        # vm flavor
        self.vm_flavor, created = VMFlavor.objects.get_or_create(name=self.vm_flavor_name)
        self.log_creation(created, 'VMFlavor', self.vm_flavor_name, self.vm_flavor.id)
        # vm_project
        self.vm_project, created = VMProject.objects.get_or_create(name=self.vm_project_name)
        self.log_creation(created, 'VMProject', self.vm_project_name, self.vm_project.id)
        # share group
        self.share_group, created = ShareGroup.objects.get_or_create(name=self.share_group_name)
        self.log_creation(created, 'ShareGroup', self.share_group_name, self.share_group.id)

        # Extract fields that are not system-provided
        user_fields = []
        document = CWLDocument(self.workflow_version.url)
        for input_field in document.input_fields:
            if not input_field.get('name') in self.system_job_order_dict:
                user_fields.append(input_field)

        # Job questionnaire
        self.job_questionnaire, created = JobQuestionnaire.objects.get_or_create(
            name=self.name,
            description=self.description,
            workflow_version=self.workflow_version,
            system_job_order_json=json.dumps(self.system_job_order_dict),
            user_fields_json=json.dumps(user_fields),
            vm_flavor=self.vm_flavor,
            vm_project=self.vm_project,
            share_group=self.share_group,
            volume_size_base=self.volume_size_base,
            volume_size_factor=self.volume_size_factor,
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
                 cwl_url,
                 version_number=1,
                 methods_jinja_template_url=None,
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
        self.cwl_url = cwl_url
        self.version_number = version_number
        self.methods_jinja_template_url = methods_jinja_template_url
        # django model objects built up
        self.workflow = None
        self.workflow_version = None

    def _create_models(self):
        document = CWLDocument(self.cwl_url)
        # Short description used for the Workflow name
        workflow_name = document.get('label')
        # Longer description used in workflow version
        workflow_version_description = document.get('doc')
        workflow, created = Workflow.objects.get_or_create(name=workflow_name)
        self.log_creation(created, 'Workflow', workflow_name, workflow.id)
        workflow_version, created = WorkflowVersion.objects.get_or_create(
            workflow=workflow,
            url=self.cwl_url,
            description=workflow_version_description,
            version=self.version_number,
        )
        software_requirement_hints = document.extract_tool_hints(hint_class_name="SoftwareRequirement")
        methods_document = MethodsDocumentContents(software_requirement_hints,
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


class Command(BaseCommand):
    help = 'Imports a workflow from CWL and creates a questionnaire. Will not alter existing model objects if they exist'

    def add_arguments(self, parser):
        parser.add_argument('cwl-url', help='URL to packed CWL workflow file. Do not include #main')
        parser.add_argument('version-number', help='Version number to assign to imported workflow')
        parser.add_argument('name', help='Short name to display forquestionnaire (e.g. ABC Processing on hg37)')
        parser.add_argument('description', help='Detailed user facing description of questionnaire')
        parser.add_argument('system-job-order-file', help='JSON Job order with system answers to associate with questionnaire '
                                                   '(e.g. reference genome files)', type=FileType('r'))
        parser.add_argument('vm-flavor', help='Name of VM flavor to use when running jobs(e.g. \'m1.large\')')
        parser.add_argument('vm-project', help='Name of Openstack to use when running jobs')
        parser.add_argument('share-group', help='Name of Share group to attach to the job questionnaire')
        parser.add_argument('volume-size-base', help='Base volume size (in GB) used for this workflow.')
        parser.add_argument('volume-size-factor', help='Integer factor multiplied by input data size when running this workflow.')
        parser.add_argument('methods-jinja-template-url',
                            help='URL that references a jinja2 template used to build the methods markdown file for this workflow.')

    def handle(self, *args, **options):
        wf_importer = WorkflowImporter(options.get('cwl-url'),
                                       version_number=options.get('version-number'),
                                       methods_jinja_template_url=options.get('methods-jinja-template-url'),
                                       stdout=self.stdout,
                                       stderr=self.stderr)
        wf_importer.run()
        jq_importer = JobQuestionnaireImporter(
            options.get('name'),
            options.get('description'),
            wf_importer.workflow_version,
            options.get('system-job-order-file'),
            options.get('vm-flavor'),
            options.get('vm-project'),
            options.get('share-group'),
            options.get('volume-size-base'),
            options.get('volume-size-factor'),
            stdout=self.stdout,
            stderr=self.stderr,
        )
        jq_importer.run()
