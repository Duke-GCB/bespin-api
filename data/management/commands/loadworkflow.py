from django.core.management.base import BaseCommand
from argparse import FileType
from data.importers import WorkflowImporter, JobQuestionnaireImporter, CWLDocument
import json


class Command(BaseCommand):
    help = 'Imports a workflow from CWL and creates a questionnaire. Will not alter existing model objects if they exist'

    def add_arguments(self, parser):
        parser.add_argument('cwl-url', help='URL to packed CWL workflow file. Do not include #main')
        parser.add_argument('version-number', help='Version number to assign to imported workflow')
        parser.add_argument('name', help='Short name to display for questionnaire (e.g. ABC Processing on hg37)')
        parser.add_argument('description', help='Detailed user facing description of questionnaire')
        parser.add_argument('system-job-order-file', help='JSON Job order with system answers to associate with questionnaire '
                                                   '(e.g. reference genome files)', type=FileType('r'))
        parser.add_argument('vm-flavor', help='Name of VM flavor to use when running jobs(e.g. \'m1.large\')')
        parser.add_argument('vm-settings', help='Name of JobSettings to use when running jobs')
        parser.add_argument('share-group', help='Name of Share group to attach to the job questionnaire')
        parser.add_argument('volume-size-base', help='Base volume size (in GB) used for this workflow.')
        parser.add_argument('volume-size-factor', help='Integer factor multiplied by input data size when running this workflow.')
        parser.add_argument('methods-jinja-template-url',
                            help='URL that references a jinja2 template used to build the methods markdown file for this workflow.')

    def handle(self, *args, **options):
        cwl_document = CWLDocument(options.get('cwl-url'))
        wf_importer = WorkflowImporter(cwl_document,
                                       version_number=options.get('version-number'),
                                       methods_jinja_template_url=options.get('methods-jinja-template-url'),
                                       stdout=self.stdout,
                                       stderr=self.stderr)
        wf_importer.run()
        jq_importer = JobQuestionnaireImporter(
            options.get('name'),
            options.get('description'),
            wf_importer.workflow_version,
            json.load(options.get('system-job-order-file')),
            options.get('vm-settings'),
            options.get('vm-flavor'),
            options.get('share-group'),
            options.get('volume-size-base'),
            options.get('volume-size-factor'),
            cwl_document,
            stdout=self.stdout,
            stderr=self.stderr,
        )
        jq_importer.run()
