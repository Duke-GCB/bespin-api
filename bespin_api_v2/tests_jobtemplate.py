from django.test import TestCase
from rest_framework.exceptions import ValidationError
from bespin_api_v2.jobtemplate import WorkflowVersionConfiguration, JobTemplate, InvalidWorkflowTagException, \
    JobOrderWalker, JobOrderValuesCheck, JobTemplateValidator, STRING_VALUE_PLACEHOLDER, INT_VALUE_PLACEHOLDER, \
    FILE_PLACEHOLDER, REQUIRED_ERROR_MESSAGE, PLACEHOLDER_ERROR_MESSAGE
from mock import patch, ANY, Mock, call


class WorkflowVersionConfigurationTestCase(TestCase):
    def test_split_workflow_tag_parts(self):
        self.assertEqual(WorkflowVersionConfiguration.split_workflow_tag_parts("exome/v1/human"), ('exome', 1, 'human'))
        self.assertEqual(WorkflowVersionConfiguration.split_workflow_tag_parts("exome/v2/mouse"), ('exome', 2, 'mouse'))
        for invalid_tag in ["", "exome", "exome/v1/human/other"]:
            with self.assertRaises(InvalidWorkflowTagException):
                WorkflowVersionConfiguration.split_workflow_tag_parts(invalid_tag)

    @patch('bespin_api_v2.jobtemplate.WorkflowVersion')
    @patch('bespin_api_v2.jobtemplate.WorkflowConfiguration')
    def test_constructor(self, mock_workflow_configuration, mock_workflow_version):
        item = WorkflowVersionConfiguration("exome/v1/human")
        mock_workflow_configuration.objects.get.assert_called_with(tag='human', workflow=ANY)
        mock_workflow_version.objects.get.assert_called_with(version=1, workflow__tag='exome')
        self.assertEqual(item.workflow_version, mock_workflow_version.objects.get.return_value)
        self.assertEqual(item.workflow_configuration, mock_workflow_configuration.objects.get.return_value)

    @patch('bespin_api_v2.jobtemplate.WorkflowVersion')
    @patch('bespin_api_v2.jobtemplate.WorkflowConfiguration')
    def test_user_job_fields(self, mock_workflow_configuration, mock_workflow_version):
        item = WorkflowVersionConfiguration("exome/v1/human")
        item.workflow_configuration.system_job_order = {"field1": "A", "field3": "C"}
        item.workflow_version.fields = [
            {"name": "field1"},
            {"name": "field2"},
            {"name": "field3"},
        ]
        self.assertEqual(item.user_job_fields(), [{'name': 'field2'}])


class JobTemplateTestCase(TestCase):
    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_create_job_order(self, mock_workflow_version_configuration):
        user_fields = [
            {"type": "int", "name": "myint"},
            {"type": "string", "name": "mystr"},
            {"type": {"type": "array",  "items": "int"}, "name": "intary"},
            {"name": "interval_padding", "type": [ "null", "int"]},
            {"name": "two_d_ary", "type": {"type": "array", "items": {"type": "array", "items": "int"}}},
        ]
        job_template = JobTemplate(tag="exome/v1/human", job_order={})
        mock_workflow_version_configuration.return_value.user_job_fields.return_value = user_fields
        job_template.populate_job_order()
        self.assertEqual(job_template.job_order, {
            'intary': [INT_VALUE_PLACEHOLDER],
            'myint': INT_VALUE_PLACEHOLDER,
            'mystr': STRING_VALUE_PLACEHOLDER,
            'two_d_ary': [[INT_VALUE_PLACEHOLDER]],
        })

    def test_create_placeholder_value(self):
        job_template = JobTemplate(tag="exome/v1/human", job_order={"A": "B"})
        self.assertEqual(
            job_template.create_placeholder_value(type_value='string'),
            STRING_VALUE_PLACEHOLDER)
        self.assertEqual(
            job_template.create_placeholder_value(type_value='int'),
            INT_VALUE_PLACEHOLDER)
        self.assertEqual(
            job_template.create_placeholder_value(type_value={'type': 'array', 'items': 'int'}),
            [INT_VALUE_PLACEHOLDER])
        self.assertEqual(
            job_template.create_placeholder_value(type_value='File'),
            {
                "class": "File",
                "path": FILE_PLACEHOLDER
            })
        self.assertEqual(
            job_template.create_placeholder_value(type_value={'type': 'array', 'items': 'File'}),
            [{
                "class": "File",
                "path": FILE_PLACEHOLDER
            }])
        self.assertEqual(
            job_template.create_placeholder_value(type_value='NamedFASTQFilePairType'),
            {
                "name": STRING_VALUE_PLACEHOLDER,
                "file1": {
                    "class": "File",
                    "path": FILE_PLACEHOLDER
                },
                "file2": {
                    "class": "File",
                    "path": FILE_PLACEHOLDER
                }
            })
        self.assertEqual(
            job_template.create_placeholder_value(type_value={'type': 'array', 'items': 'NamedFASTQFilePairType'}),
            [{
                "name": STRING_VALUE_PLACEHOLDER,
                "file1": {
                    "class": "File",
                    "path": FILE_PLACEHOLDER
                },
                "file2": {
                    "class": "File",
                    "path": FILE_PLACEHOLDER
                }
            }])

    def test_create_placeholder_value_dicts(self):
        job_template = JobTemplate(tag="exome/v1/human", job_order={"A": "B"})
        self.assertEqual(
            job_template.create_placeholder_value(["null", "int"]),
            None
        )
        with self.assertRaises(ValueError):
            job_template.create_placeholder_value(["int"])

    def test_create_placeholder_value_nested_array(self):
        job_template = JobTemplate(tag="exome/v1/human", job_order={"A": "B"})
        array_2D = {
            "type": "array",
            "items": {
                "type": "array",
                "items": "File"
            }
        }
        self.assertEqual(
            job_template.create_placeholder_value(array_2D),
            [[{'class': 'File', 'path': 'dds://<Project Name>/<File Path>'}]]
        )

        array_3D = {
            "type": "array",
            "items": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": "int"
                }
            }
        }
        self.assertEqual(
            job_template.create_placeholder_value(array_3D),
            [[['<Integer Value>']]]
        )

    def test_create_placeholder_value_unknown_types(self):
        job_template = JobTemplate(tag="exome/v1/human", job_order={"A": "B"})

        with self.assertRaises(ValueError):
            job_template.create_placeholder_value(["junk"])  # array without null

        with self.assertRaises(ValueError):
            job_template.create_placeholder_value({'type': 'unknown'})  # dictionary with non-array type

    def test_get_job_strategy(self):
        mock_workflow_configuration = Mock(default_job_strategy='good')
        job_order_data = JobTemplate(tag=None, name=None, fund_code=None, stage_group=None, job_order=None,
                                     job_vm_strategy=None)
        self.assertEqual(job_order_data.get_job_strategy(mock_workflow_configuration), 'good')
        job_order_data = JobTemplate(tag=None, name=None, fund_code=None, stage_group=None, job_order=None,
                                     job_vm_strategy='special')
        self.assertEqual(job_order_data.get_job_strategy(mock_workflow_configuration), 'special')

    @patch('bespin_api_v2.jobtemplate.JobFactory')
    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_create_job_factory(self, mock_workflow_version_configuration, mock_job_factory):
        job_template = JobTemplate(tag=None, name=None, fund_code=None, stage_group=None, job_order=None,
                                   job_vm_strategy=None)
        self.assertEqual(job_template.create_job_factory(user=None), mock_job_factory.return_value)
        workflow_version = mock_workflow_version_configuration.return_value.workflow_version
        workflow_configuration = mock_workflow_version_configuration.return_value.workflow_configuration
        mock_job_factory.assert_called_with(None, workflow_version, None, None, None,
                                            workflow_configuration.system_job_order, None,
                                            workflow_configuration.default_job_strategy,
                                            workflow_configuration.share_group)

    @patch('bespin_api_v2.jobtemplate.JobFactory')
    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_create_job(self, mock_workflow_version_configuration, mock_job_factory):
        job_template = JobTemplate(tag=None, name=None, fund_code=None, stage_group=None, job_order=None,
                                   job_vm_strategy=None)
        self.assertEqual(job_template.job, None)
        job_template.create_and_populate_job(Mock())
        self.assertEqual(job_template.job, mock_job_factory.return_value.create_job.return_value)


class JobTemplateValidatorTestCase(TestCase):
    @patch('bespin_api_v2.jobtemplate.JobOrderValuesCheck')
    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_run_null_required_fields(self, mock_workflow_version_configuration, mock_job_order_values_check):
        mock_workflow_version_configuration.return_value.user_job_fields.return_value = []
        mock_job_order_values_check.return_value = Mock(errors=[])
        validator = JobTemplateValidator({
            'tag': 'exome/v1/human',
        })
        with self.assertRaises(ValidationError) as raised_exception:
            validator.run()
        self.assertEqual(raised_exception.exception.detail, {
            'name': [REQUIRED_ERROR_MESSAGE],
            'fund_code': [REQUIRED_ERROR_MESSAGE],
            'job_order': [REQUIRED_ERROR_MESSAGE],
        })

    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_run_with_placeholders(self, mock_workflow_version_configuration):
        mock_workflow_version_configuration.return_value.user_job_fields.return_value = []
        validator = JobTemplateValidator({
            'tag': 'exome/v1/human',
            'name': STRING_VALUE_PLACEHOLDER,
            'fund_code': STRING_VALUE_PLACEHOLDER,
            'job_order': {
                'threads': INT_VALUE_PLACEHOLDER
            }
        })
        with self.assertRaises(ValidationError) as raised_exception:
            validator.run()
        self.assertEqual(raised_exception.exception.detail, {
            'name': [PLACEHOLDER_ERROR_MESSAGE],
            'fund_code': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.threads': [PLACEHOLDER_ERROR_MESSAGE],
        })

    @patch('bespin_api_v2.jobtemplate.JobOrderValuesCheck')
    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_run(self, mock_workflow_version_configuration, mock_job_order_values_check):
        mock_workflow_version_configuration.return_value.user_job_fields.return_value = []
        mock_job_order_values_check.return_value = Mock(errors=[])
        validator = JobTemplateValidator({
            'tag': 'exome/v1/human',
            'name': 'myjob',
            'fund_code': '001',
            'job_order': {
                'threads': 12
            }
        })
        validator.run()

    @patch('bespin_api_v2.jobtemplate.WorkflowVersionConfiguration')
    def test_run_check_job_order_values(self, mock_workflow_version_configuration):
        mock_workflow_version_configuration.return_value.user_job_fields.return_value = [{"name":"bad_field"}]
        validator = JobTemplateValidator({
            'tag': 'exome/v1/human',
            'name': 'myjob',
            'fund_code': '001',
            'job_order': {
                'threads': 12
            }
        })
        with self.assertRaises(ValidationError) as raised_exception:
            validator.run()
        self.assertEqual(raised_exception.exception.detail, {
            'job_order.bad_field': [REQUIRED_ERROR_MESSAGE]
        })

    def test_is_placeholder_value(self):
        self.assertEqual(JobTemplateValidator.is_placeholder_value("<String Value>"), True)
        self.assertEqual(JobTemplateValidator.is_placeholder_value("<Integer Value>"), True)
        self.assertEqual(JobTemplateValidator.is_placeholder_value("dds://<Project Name>/<File Path>"), True)
        self.assertEqual(JobTemplateValidator.is_placeholder_value("test"), False)
        self.assertEqual(JobTemplateValidator.is_placeholder_value(123), False)


class JobOrderWalkerTestCase(TestCase):
    def test_walk(self):
        walker = JobOrderWalker()
        walker.on_class_value = Mock()
        walker.on_simple_value = Mock()
        walker.walk({
            'color': 'red',
            'weight': 123,
            'file1': {
                'class': 'File',
                'path': 'somepath'
            },
            'file_ary': [
                {
                    'class': 'File',
                    'path': 'somepath1'
                }, {
                    'class': 'File',
                    'path': 'somepath2'
                },
            ],
            'nested': {
                'a': [{
                    'class': 'File',
                    'path': 'somepath3'
                }]
            },
            'plain_path_file': {
                'class': 'File',
                'path': '/tmp/data.txt'
            },
            'url_file': {
                'class': 'File',
                'location': 'https://github.com/datafile1.dat'
            },
        })

        walker.on_simple_value.assert_has_calls([
            call('color', 'red'),
            call('weight', 123),
        ])
        walker.on_class_value.assert_has_calls([
            call('file1', {'class': 'File', 'path': 'somepath'}),
            call('file_ary', {'class': 'File', 'path': 'somepath1'}),
            call('file_ary', {'class': 'File', 'path': 'somepath2'}),
            call('nested', {'class': 'File', 'path': 'somepath3'}),
        ])

    def test_format_file_path(self):
        data = [
            # input    expected
            ('https://placeholder.data/stuff/data.txt', 'https://placeholder.data/stuff/data.txt'),
            ('dds://myproject/rawData/SAAAA_R1_001.fastq.gz', 'dds_myproject_rawData_SAAAA_R1_001.fastq.gz'),
            ('dds://project/somepath.txt', 'dds_project_somepath.txt'),
            ('dds://project/dir/somepath.txt', 'dds_project_dir_somepath.txt'),
        ]
        for input_val, expected_val in data:
            self.assertEqual(JobOrderWalker.format_file_path(input_val), expected_val)


class JobOrderValuesCheckTestCase(TestCase):
    def test_walk(self):
        job_order = {
            'good_str': 'a',
            'bad_str': STRING_VALUE_PLACEHOLDER,
            'good_int': 123,
            'bad_int': INT_VALUE_PLACEHOLDER,
            'good_file': {
                'class': 'File',
                'path': 'somepath.txt',
            },
            'bad_file': {
                'class': 'File',
                'path': FILE_PLACEHOLDER,
            },
            'good_str_ary': ['a', 'b', 'c'],
            'bad_str_ary': ['a', STRING_VALUE_PLACEHOLDER, 'c'],
            'good_file_ary': [{
                'class': 'File',
                'path': 'somepath.txt',
            }],
            'bad_file_ary': [{
                'class': 'File',
                'path': FILE_PLACEHOLDER,
            }],
            'good_file_dict': {
                'stuff': {
                    'class': 'File',
                    'path': 'somepath.txt',
                }
            },
            'bad_file_dict': {
                'stuff': {
                    'class': 'File',
                    'path': FILE_PLACEHOLDER,
                }
            },
            'plain_path_file': {
                'class': 'File',
                'path': '/tmp/data.txt'
            },
            'url_file': {
                'class': 'File',
                'location': 'https://github.com/datafile1.dat'
            },
        }
        expected_keys = {
            'job_order.bad_str': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.bad_int': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.bad_file': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.bad_str_ary': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.bad_file_ary': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.bad_file_dict': [PLACEHOLDER_ERROR_MESSAGE],
            'job_order.missing_field': [REQUIRED_ERROR_MESSAGE],
        }

        checker = JobOrderValuesCheck(user_job_fields=[{'name': 'missing_field'}])
        checker.walk(job_order)

        self.assertEqual(checker.errors, expected_keys)
