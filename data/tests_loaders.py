from __future__ import absolute_import
from django.test import TestCase
from data.loaders import CWLDocument, MethodsDocumentContents, SCHEMA_ORG_CITATION, \
    HTTPS_DOI_URL, QuestionnaireLoader, LoaderException
from data.models import ShareGroup
from data.tests_api import add_vm_settings
from mock import patch, Mock


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
    @patch('data.loaders.requests')
    @patch('data.loaders.cn')
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


class QuestionnaireLoaderTestCase(TestCase):

    def test_raises_on_vm_settings_name_not_found(self):
        ShareGroup.objects.create(name='test-share-group')
        data = {
            'vm_settings_name': 'missing',
            'share_group_name': 'test-share-group'
        }
        loader = QuestionnaireLoader(data)
        with self.assertRaises(LoaderException) as cm:
            loader.run()
        self.assertIn('VMSettings', cm.exception.message)

    def test_raises_share_group_namenot_found(self):
        add_vm_settings(self, settings_name='test-vm-settings')
        data = {
            'vm_settings_name': self.vm_settings.name,
            'share_group_name': 'missing'
        }
        loader = QuestionnaireLoader(data)
        with self.assertRaises(LoaderException) as cm:
            loader.run()
        self.assertIn('ShareGroup', cm.exception.message)

    @patch('data.loaders.WorkflowImporter')
    @patch('data.loaders.JobQuestionnaireImporter')
    def test_runs_load(self, mock_job_questionnaire_importer, mock_workflow_importer):
        mock_wfi_run = Mock()
        mock_workflow_importer.return_value.run = mock_wfi_run
        mock_workflow_version = Mock()
        mock_workflow_importer.return_value.workflow_version = mock_workflow_version
        mock_jqi_run = Mock()
        mock_job_questionnaire_importer.return_value.run = mock_jqi_run

        add_vm_settings(self, settings_name='test-settings')
        self.share_group = ShareGroup.objects.create(name='test-share-group')
        data = {
            "cwl_url": "https://example.org/exome-seq.cwl",
            "workflow_version_number": 12,
            "name": "Test Questionnaire Name",
            "description": "Test Questionnaire Description",
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
            "vm_settings_name": self.vm_settings.name,
            "vm_flavor_name": "test-flavor",
            "share_group_name": self.share_group.name,
            "volume_size_base": 100,
            "volume_size_factor": 10
        }

        loader = QuestionnaireLoader(data)
        loader.run()

        # Check that the workflow importer was called with the cwl_url, workflow_version_number, and methods_template_url
        args, kwargs = mock_workflow_importer.call_args
        self.assertEqual(args, (data['cwl_url'], data['workflow_version_number'], data['methods_template_url'],))
        self.assertEqual(kwargs, {})
        self.assertTrue(mock_wfi_run.called)

        # Check that the Job Questionnaire Importer was called
        args, kwargs = mock_job_questionnaire_importer.call_args
        self.assertEqual(args, (
            data['name'],
            data['description'],
            mock_workflow_version,
            data['system_json'],
            data['vm_settings_name'],
            data['vm_flavor_name'],
            data['share_group_name'],
            data['volume_size_base'],
            data['volume_size_factor'],
        ))
        self.assertEqual(kwargs, {})
        self.assertTrue(mock_jqi_run.called)

    def test_raises_exceptions(self):
        self.fail('not yet implemented')

