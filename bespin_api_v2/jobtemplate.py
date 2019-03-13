from data.jobfactory import JobFactory
from data.exceptions import InvalidWorkflowTagException
from data.models import WorkflowVersion, WorkflowConfiguration
from rest_framework.fields import Field
from rest_framework.serializers import ValidationError
import six

DUKEDS_PATH_PREFIX = "dds://"
STRING_VALUE_PLACEHOLDER = "<String Value>"
INT_VALUE_PLACEHOLDER = "<Integer Value>"
FILE_PLACEHOLDER = "dds://<Project Name>/<File Path>"
USER_PLACEHOLDER_VALUES = [STRING_VALUE_PLACEHOLDER, INT_VALUE_PLACEHOLDER, FILE_PLACEHOLDER]
USER_PLACEHOLDER_DICT = {
    'File': {
        "class": "File",
        "path": FILE_PLACEHOLDER
    },
    'int': INT_VALUE_PLACEHOLDER,
    'string': STRING_VALUE_PLACEHOLDER,
    'NamedFASTQFilePairType': {
        "name": STRING_VALUE_PLACEHOLDER,
        "file1": {
            "class": "File",
            "path": FILE_PLACEHOLDER
        },
        "file2": {
            "class": "File",
            "path": FILE_PLACEHOLDER
        }
    },
    'FASTQReadPairType': {
        "name": STRING_VALUE_PLACEHOLDER,
        "read1_files": [{
            "class": "File",
            "path": FILE_PLACEHOLDER
        }],
        "read2_files": [{
            "class": "File",
            "path": FILE_PLACEHOLDER
        }]
    }
}
REQUIRED_ERROR_MESSAGE = str(Field.default_error_messages['required'])
PLACEHOLDER_ERROR_MESSAGE = 'This field contains a placeholder value.'


class WorkflowVersionConfiguration(object):
    def __init__(self, tag):
        workflow_tag, version_num, configuration_name = self.split_workflow_tag_parts(tag)
        self.workflow_version = WorkflowVersion.objects.get(
            version=version_num,
            workflow__tag=workflow_tag)
        self.workflow_configuration = WorkflowConfiguration.objects.get(
            workflow=self.workflow_version.workflow,
            tag=configuration_name)

    @staticmethod
    def split_workflow_tag_parts(tag):
        """
        Based on our tag return tuple of base_workflow_tag, version_num, configuration_name
        :param tag: str: tag to split into parts
        :return: (workflow_tag, version_num, configuration_name)
        """
        parts = tag.split("/")
        if len(parts) != 3:
            raise InvalidWorkflowTagException("Invalid workflow tag {}".format(tag))
        workflow_tag, version_num_str, configuration_name = parts
        version_num = int(version_num_str.replace("v", ""))
        return workflow_tag, version_num, configuration_name

    def user_job_fields(self):
        system_keys = self.workflow_configuration.system_job_order.keys()
        user_fields_json = []
        for field in self.workflow_version.fields:
            if field['name'] not in system_keys:
                user_fields_json.append(field)
        return user_fields_json


class JobTemplate(object):
    def __init__(self, tag, name=STRING_VALUE_PLACEHOLDER, fund_code=STRING_VALUE_PLACEHOLDER,
                 stage_group=None, job_order=None, job_strategy=None):
        self.tag = tag
        self.name = name
        self.fund_code = fund_code
        self.stage_group = stage_group
        self.job_order = job_order
        self.job_strategy = job_strategy
        self.job = None

    def populate_job_order(self):
        workflow_version_config = WorkflowVersionConfiguration(self.tag)
        formatted_user_fields = {}
        for user_field in workflow_version_config.user_job_fields():
            field_type = user_field.get('type')
            field_name = user_field.get('name')
            value = self.create_placeholder_value(field_type)
            if value:
                formatted_user_fields[field_name] = value
        self.job_order = formatted_user_fields

    def create_placeholder_value(self, type_value):
        if isinstance(type_value, six.string_types):
            placeholder = USER_PLACEHOLDER_DICT.get(type_value)
            if not placeholder:
                placeholder = STRING_VALUE_PLACEHOLDER
            return placeholder
        elif isinstance(type_value, list):
            first_element = type_value[0]
            if first_element == "null":
                return None
        elif isinstance(type_value, dict):
            if type_value['type'] == 'array':
                return [self.create_placeholder_value(type_value['items'])]
        raise ValueError("Unknown type {}".format(type_value))

    def get_job_strategy(self, workflow_configuration):
        if self.job_strategy:
            return self.job_strategy
        else:
            return workflow_configuration.default_job_strategy

    def create_job_factory(self, user):
        workflow_version_configuration = WorkflowVersionConfiguration(self.tag)
        workflow_configuration = workflow_version_configuration.workflow_configuration
        system_job_order = workflow_configuration.system_job_order
        job_strategy = self.get_job_strategy(workflow_configuration)
        return JobFactory(user, workflow_version_configuration.workflow_version,
                          self.name, self.fund_code, self.stage_group,
                          system_job_order, self.job_order,
                          job_strategy, workflow_configuration.share_group)

    def create_and_populate_job(self, user):
        job_factory = self.create_job_factory(user)
        self.job = job_factory.create_job()


class JobTemplateValidator(object):
    def __init__(self, data):
        self.data = data
        self.errors = {}

    def run(self):
        self.validate_required_field('name')
        self.validate_required_field('fund_code')
        self.validate_job_order()
        if self.errors:
            raise ValidationError(self.errors)

    def validate_required_field(self, key):
        value = self.data.get(key)
        if not value:
            self.errors[key] = [REQUIRED_ERROR_MESSAGE]
        elif self.is_placeholder_value(value):
            self.errors[key] = [PLACEHOLDER_ERROR_MESSAGE]

    def validate_job_order(self):
        job_order = self.data.get('job_order')
        if job_order:
            user_job_fields = self.get_user_job_fields()
            checker = JobOrderValuesCheck(user_job_fields)
            checker.walk(job_order)
            self.errors.update(checker.errors)
        else:
            self.errors['job_order'] = [REQUIRED_ERROR_MESSAGE]

    def get_user_job_fields(self):
        tag = self.data['tag']
        return WorkflowVersionConfiguration(tag).user_job_fields()

    @staticmethod
    def is_placeholder_value(value):
        return value in USER_PLACEHOLDER_VALUES


class JobOrderWalker(object):
    def walk(self, obj):
        for key in obj.keys():
            self._walk_job_order(key, obj[key])

    def _walk_job_order(self, top_level_key, obj):
        if self._is_list_but_not_string(obj):
            return [self._walk_job_order(top_level_key, item) for item in obj]
        elif isinstance(obj, dict):
            if 'class' in obj.keys():
                self.on_class_value(top_level_key, obj)
            else:
                for key in obj:
                    self._walk_job_order(top_level_key, obj[key])
        else:
            # base object string or int or something
            self.on_simple_value(top_level_key, obj)

    @staticmethod
    def _is_list_but_not_string(obj):
        return isinstance(obj, list) and not isinstance(obj, str)

    def on_class_value(self, top_level_key, value):
        pass

    def on_simple_value(self, top_level_key, value):
        pass

    @staticmethod
    def format_file_path(path):
        """
        Create a valid file path based on a dds placeholder url
        :param path: str: format dds://<projectname>/<filepath>
        :return: str: file path to be used for staging data when running the workflow
        """
        if path.startswith(DUKEDS_PATH_PREFIX):
            return path.replace(DUKEDS_PATH_PREFIX, "dds_").replace("/", "_").replace(":", "_")
        return path


class JobOrderValuesCheck(JobOrderWalker):
    def __init__(self, user_job_fields):
        self.user_job_fields = user_job_fields
        #self.user_job_keys = [field['name'] for field in user_job_fields]
        self.errors = {}

    def walk(self, obj):
        for job_field in self.user_job_fields:
            field_name = job_field['name']
            field_type = job_field['type']
            if self.is_required_type(field_type) and not field_name in obj:
                    self._on_bad_value(field_name, REQUIRED_ERROR_MESSAGE)
        super(JobOrderValuesCheck, self).walk(obj)

    def is_required_type(self, field_type):
        if isinstance(field_type, list) and field_type[0] == "null":
            return False
        return True

    def on_class_value(self, top_level_key, value):
        if value['class'] == 'File':
            path = value.get('path')
            if path and JobTemplateValidator.is_placeholder_value(path):
                self._on_bad_value(top_level_key, PLACEHOLDER_ERROR_MESSAGE)

    def on_simple_value(self, top_level_key, value):
        if JobTemplateValidator.is_placeholder_value(value):
            self._on_bad_value(top_level_key, PLACEHOLDER_ERROR_MESSAGE)

    def _on_bad_value(self, key, error_message):
        complete_name = 'job_order.{}'.format(key)
        self.errors[complete_name] = [error_message]
