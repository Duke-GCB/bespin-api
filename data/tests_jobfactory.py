from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError
from mock.mock import MagicMock, patch, Mock
from models import DDSEndpoint, DDSUserCredential, Workflow, WorkflowVersion
from jobfactory import JobFactory, JobFactoryException
import json


FLY_RNASEQ_URL = "https://raw.githubusercontent.com/Duke-GCB/bespin-cwl/master/packed-workflows/rnaseq-pt1-packed.cwl"

class JobFactoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_user')
        self.endpoint = DDSEndpoint.objects.create(name='app1', agent_key='abc123')
        self.cred = DDSUserCredential.objects.create(user=self.user, token='abc123', endpoint=self.endpoint)
        workflow = Workflow.objects.create(name='RnaSeq')
        self.workflow_version = WorkflowVersion.objects.create(workflow=workflow,
                                                               object_name='#main',
                                                               version='1',
                                                               url=FLY_RNASEQ_URL)

    # What does job factory do now?
    # Checks that orders are not none
    # merges dictionaries
    # Creates a job

    def test_requires_user_order(self):
        user_job_order = None
        system_job_order = {}
        job_factory = JobFactory(self.user, None, user_job_order, system_job_order, None, None, None)
        with self.assertRaises(JobFactoryException):
            job_factory.create_job()


    def test_requires_system_order(self):
        user_job_order = {}
        system_job_order = None
        job_factory = JobFactory(self.user, None, user_job_order, system_job_order, None, None, None)
        with self.assertRaises(JobFactoryException):
            job_factory.create_job()

    def test_creates_job(self):
        user_job_order = {'input1': 'user'}
        system_job_order = {'input2' : 'system'}
        job_factory = JobFactory(self.user, self.workflow_version, user_job_order, system_job_order, 'Test Job', 'bespin-project', 'flavor1')
        job = job_factory.create_job()
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.workflow_version, self.workflow_version)
        expected_job_order = json.dumps({'input1':'user','input2':'system'})
        self.assertEqual(expected_job_order, job.job_order)
        self.assertEqual(job.name, 'Test Job')
        self.assertEqual(job.vm_project_name, 'bespin-project')
        self.assertEqual(job.vm_flavor,'flavor1')

    def test_favors_user_inputs(self):
        user_job_order = {'input1': 'user'}
        system_job_order = {'input1' : 'system'}
        job_factory = JobFactory(self.user, self.workflow_version, user_job_order, system_job_order, 'Test Job', 'bespin-project', 'flavor1')
        job = job_factory.create_job()
        expected_job_order = json.dumps({'input1':'user'})
        self.assertEqual(expected_job_order, job.job_order)
