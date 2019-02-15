from django.test import TestCase
from data.importers import CWLDocument, MethodsDocumentContents, SCHEMA_ORG_CITATION, \
    HTTPS_DOI_URL, WorkflowQuestionnaireImporter, ImporterException
from data.models import ShareGroup
from data.tests_api import add_job_settings
from unittest.mock import patch, Mock


class CWLNodeWithSteps(object):
    def __init__(self, steps):
        self.steps = steps


class CWLStepNode(object):
    def __init__(self, embedded_tool):
        self.embedded_tool = embedded_tool


class CWLNodeWithHints(object):
    def __init__(self, hints):
        self.hints = hints


class CWLDocumentTestCase(TestCase):
    def test_extract_tool_hints(self):
        cwl_document = CWLDocument('someurl')
        step_node1 = CWLStepNode(embedded_tool=CWLNodeWithHints(hints=[
            {
                'class': 'specialHint', 'value': 1
            }
        ]))
        step_node2 = CWLStepNode(embedded_tool=CWLNodeWithHints(hints=[
            {
                'class': 'specialHint', 'value': 2
            }
        ]))
        cwl_document._parsed = CWLNodeWithSteps(
            steps=[
                step_node1,
                CWLStepNode(
                    embedded_tool=CWLNodeWithSteps(
                        steps=[
                            step_node2
                        ]
                    )
                )
            ]
        )
        hints = cwl_document.extract_tool_hints('specialHint')
        self.assertEqual(set([1, 2]), set([hint['value'] for hint in hints]))


class MethodsDocumentContentsTestCase(TestCase):
    @patch('data.importers.requests')
    @patch('data.importers.cn')
    def test_get_content(self, mock_cn, mock_requests):

        software_requirement_hints = [
            {
                'packages': [
                    {
                        'package': 'sometool',
                        'version': '1',
                        SCHEMA_ORG_CITATION: 'someurl'
                    },
                    {
                        'package': 'othertool',
                        'version': '3',
                        SCHEMA_ORG_CITATION: HTTPS_DOI_URL + 'mydoi123'
                    },
                ]
            }
        ]
        jinja_template = """desc: {{description}} sometool version:{{sometool.version}} citation: {{sometool.citation}}
othertool version: {{othertool.version}} citation: {{othertool.citation}}"""
        expected_content = """desc: A good workflow sometool version:1 citation: someurl
othertool version: 3 citation: Dr Man 2017"""
        mock_requests.get.return_value = Mock(text=jinja_template)
        mock_cn.content_negotiation.return_value = 'Dr Man 2017'
        method_document_contents = MethodsDocumentContents(
            workflow_version_description='A good workflow',
            software_requirement_hints=software_requirement_hints,
            jinja_template_url='fakeurl')
        self.assertEqual(expected_content, method_document_contents.get_content())


class JobQuestionnaireImporterTestCase(TestCase):

    def setUp(self):
        self.share_group_name = 'test-share-group'
        self.job_settings_name = 'test-vm-settings'
        self.data = {
            "cwl_url": "https://example.org/exome-seq.cwl",
            "workflow_version_number": 12,
            "name": "Test Questionnaire Name",
            "description": "Test Questionnaire Description",
            "workflow_tag": "my-tag",
            "methods_template_url": "https://example.org/exome-seq.md.j2",
            "system_json": {
                "threads": 4,
                "files": [
                    {
                        "class": "File",
                        "path": "/nfs/data/genome.fa"
                    }
                ]
            },
            "job_settings_name": self.job_settings_name,
            "vm_flavor_name": "test-flavor",
            "share_group_name": self.share_group_name,
            "volume_size_base": 100,
            "volume_size_factor": 10,
            "type_tag": "human",
        }

    def test_raises_on_job_settings_name_not_found(self):
        ShareGroup.objects.create(name=self.share_group_name)
        self.data['job_settings_name'] = 'missing'
        importer = WorkflowQuestionnaireImporter(self.data)
        with self.assertRaises(ImporterException) as cm:
            importer.run()
        self.assertIn('JobSettings', cm.exception.message)

    def test_raises_share_group_name_not_found(self):
        add_job_settings(self, settings_name=self.job_settings_name)
        self.data['share_group_name'] = 'missing'
        importer = WorkflowQuestionnaireImporter(self.data)
        with self.assertRaises(ImporterException) as cm:
            importer.run()
        self.assertIn('ShareGroup', cm.exception.message)

    @patch('data.importers.WorkflowImporter')
    @patch('data.importers.JobQuestionnaireImporter')
    @patch('data.importers.CWLDocument')
    def test_runs_load(self, mock_cwl_document, mock_job_questionnaire_importer, mock_workflow_importer):
        mock_doc = Mock()
        mock_cwl_document.return_value = mock_doc
        mock_wfi_run = Mock()
        mock_workflow_importer.return_value.run = mock_wfi_run
        mock_workflow_version = Mock()
        mock_workflow_importer.return_value.workflow_version = mock_workflow_version
        mock_jqi_run = Mock()
        mock_job_questionnaire_importer.return_value.run = mock_jqi_run

        add_job_settings(self, settings_name=self.job_settings_name)
        self.share_group = ShareGroup.objects.create(name=self.share_group_name)

        importer = WorkflowQuestionnaireImporter(self.data)
        importer.run()

        # Check that a CWLDocument was instantiated with the cwl_url
        args, kwargs = mock_cwl_document.call_args
        self.assertEqual(args, (self.data['cwl_url'],))
        self.assertEqual(kwargs, {})
        self.assertTrue(mock_cwl_document.called)

        # Check that the workflow importer was called with the CWL Document, workflow_version_number, and methods_template_url
        args, kwargs = mock_workflow_importer.call_args
        self.assertEqual(args, (mock_doc,
                                self.data['workflow_version_number'],
                                self.data['methods_template_url'],
                                self.data['workflow_tag'],))
        self.assertEqual(kwargs, {})
        self.assertTrue(mock_wfi_run.called)

        # Check that the Job Questionnaire Importer was called
        args, kwargs = mock_job_questionnaire_importer.call_args
        self.assertEqual(args, (
            self.data['name'],
            self.data['description'],
            self.data['type_tag'],
            mock_workflow_version,
            self.data['system_json'],
            self.data['job_settings_name'],
            self.data['vm_flavor_name'],
            self.data['share_group_name'],
            self.data['volume_size_base'],
            self.data['volume_size_factor'],
            mock_doc
        ))
        self.assertEqual(kwargs, {})
        self.assertTrue(mock_jqi_run.called)


    @patch('data.importers.WorkflowImporter')
    @patch('data.importers.JobQuestionnaireImporter')
    @patch('data.importers.CWLDocument')
    def test_captures_wfimporter_exceptions(self, mock_cwl_document, mock_jobquestionnaire_importer, mock_workflow_importer):
        add_job_settings(self, settings_name=self.job_settings_name)
        self.share_group = ShareGroup.objects.create(name=self.share_group_name)
        mock_workflow_importer.side_effect = Exception()
        importer = WorkflowQuestionnaireImporter(self.data)
        with self.assertRaises(ImporterException) as cm:
            importer.run()
        self.assertIn('Unable to import workflow', cm.exception.message)

    @patch('data.importers.WorkflowImporter')
    @patch('data.importers.JobQuestionnaireImporter')
    @patch('data.importers.CWLDocument')
    def test_captures_jqimporter_exceptions(self, mock_cwl_document, mock_jobquestionnaire_importer, mock_workflow_importer):
        add_job_settings(self, settings_name=self.job_settings_name)
        self.share_group = ShareGroup.objects.create(name=self.share_group_name)
        mock_jobquestionnaire_importer.side_effect = Exception()
        importer = WorkflowQuestionnaireImporter(self.data)
        with self.assertRaises(ImporterException) as cm:
            importer.run()
        self.assertIn('Unable to import questionnaire', cm.exception.message)

