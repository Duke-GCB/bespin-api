from django.test import TestCase
from models import Job, JobActivity
import datetime
from mock import Mock, patch
from jobusage import JobUsage
from django.utils import timezone


class JobUsageTests(TestCase):
    @staticmethod
    def mock_job(activity_values, num_cpus):
        activities = []
        for state, step, created in activity_values:
            activities.append(Mock(state=state, step=step, created=created))
        mock_manager = Mock()
        mock_manager.all.return_value = activities
        return Mock(job_activities=mock_manager, vm_flavor=Mock(cpus=num_cpus))

    @staticmethod
    def created_ts(hr_min_str):
        hr, min = hr_min_str.split(':')
        return datetime.datetime(2018, 1, 1, int(hr), int(min), tzinfo=timezone.utc)

    def test_zip_job_activity_pairs(self):
        activities = [
            (Job.JOB_STATE_NEW, '', self.created_ts('12:01')),
            (Job.JOB_STATE_AUTHORIZED, '', self.created_ts('12:02')),
            (Job.JOB_STATE_RUNNING, '', self.created_ts('12:02')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STAGING, self.created_ts('12:02')),
        ]
        mock_job = self.mock_job(activities, num_cpus=32)
        pairs = JobUsage._zip_job_activity_pairs(mock_job.job_activities.all())
        self.assertEqual(len(pairs), 4)
        pair = pairs[0]
        self.assertEqual(pair[0].state, Job.JOB_STATE_NEW)  # first item is NEW
        self.assertEqual(pair[1].state, Job.JOB_STATE_AUTHORIZED)  # subsequent item is AUTHORIZED
        pair = pairs[1]
        self.assertEqual(pair[0].state, Job.JOB_STATE_AUTHORIZED)  # first item is AUTHORIZIED
        self.assertEqual(pair[1].state, Job.JOB_STATE_RUNNING)  # subsequent item is RUNNING
        pair = pairs[2]
        self.assertEqual(pair[0].state, Job.JOB_STATE_RUNNING)  # first item is RUNNING
        self.assertEqual(pair[0].step, '')  # first item is blank step
        self.assertEqual(pair[1].state, Job.JOB_STATE_RUNNING)  # subsequent item is RUNNING
        self.assertEqual(pair[1].step, Job.JOB_STEP_STAGING)  # subsequent item is RUNNING
        pair = pairs[3]
        self.assertEqual(pair[0].state, Job.JOB_STATE_RUNNING)  # subsequent item is RUNNING
        self.assertEqual(pair[0].step, Job.JOB_STEP_STAGING)  # subsequent item is RUNNING
        self.assertEqual(pair[1], None)  # last item is None because there is no next item

    def test_filtered_activity_pairs(self):
        activities = [
            (Job.JOB_STATE_NEW, '', self.created_ts('12:01')),
            (Job.JOB_STATE_AUTHORIZED, '', self.created_ts('12:02')),
            (Job.JOB_STATE_RUNNING, '', self.created_ts('12:03')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STAGING, self.created_ts('12:04')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STATE_RUNNING, self.created_ts('12:05')),
        ]
        mock_job = self.mock_job(activities, num_cpus=32)
        usage = JobUsage(mock_job)
        pairs = usage._filtered_activity_pairs(Job.JOB_STATE_RUNNING,
                                               [Job.JOB_STEP_STAGING, Job.JOB_STEP_RUNNING, Job.JOB_STEP_STORE_OUTPUT])
        self.assertEqual(len(pairs), 2)
        pair = pairs[0]
        self.assertEqual(pair[0].state, Job.JOB_STATE_RUNNING)  # first item is RUNNING
        self.assertEqual(pair[0].step, Job.JOB_STEP_STAGING)  # first item is blank step
        self.assertEqual(pair[1].state, Job.JOB_STATE_RUNNING)  # subsequent item is RUNNING
        self.assertEqual(pair[1].step, Job.JOB_STEP_RUNNING)  # subsequent item is RUNNING
        pair = pairs[1]
        self.assertEqual(pair[0].state, Job.JOB_STATE_RUNNING)  # subsequent item is RUNNING
        self.assertEqual(pair[0].step, Job.JOB_STEP_RUNNING)  # subsequent item is RUNNING
        self.assertEqual(pair[1], None)  # last item is None because there is no next item

    def test_calculate_elapsed_hours(self):
        hours = JobUsage._calculate_elapsed_hours(
            activity=Mock(created=self.created_ts('12:00')),
            next_activity=Mock(created=self.created_ts('14:30')))
        self.assertEqual(hours, 2.5)

    @patch('data.jobusage.timezone')
    def test_vm_hours_still_running(self, mock_timezone):
        activities = [
            (Job.JOB_STATE_NEW, '', self.created_ts('11:50')),
            (Job.JOB_STATE_AUTHORIZED, '', self.created_ts('11:58')),
            (Job.JOB_STATE_RUNNING, '', self.created_ts('11:59')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STAGING, self.created_ts('12:00')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_RUNNING, self.created_ts('12:30')),
        ]
        mock_job = self.mock_job(activities, num_cpus=32)
        mock_timezone.now.return_value = self.created_ts('14:30')
        usage = JobUsage(mock_job)
        self.assertEqual(usage.vm_hours, 2.5)

    @patch('data.jobusage.timezone')
    def test_vm_hours_finished(self, mock_timezone):
        activities = [
            (Job.JOB_STATE_NEW, '', self.created_ts('11:50')),
            (Job.JOB_STATE_AUTHORIZED, '', self.created_ts('11:58')),
            (Job.JOB_STATE_RUNNING, '', self.created_ts('11:59')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STAGING, self.created_ts('12:00')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_RUNNING, self.created_ts('12:30')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_TERMINATE_VM, self.created_ts('13:15')),
            (Job.JOB_STATE_FINISHED, '', self.created_ts('13:16')),
        ]
        mock_job = self.mock_job(activities, num_cpus=32)
        usage = JobUsage(mock_job)
        mock_timezone.now.return_value = self.created_ts('14:30')
        self.assertEqual(usage.vm_hours, 1.25)

    @patch('data.jobusage.timezone')
    def test_vm_hours_error(self, mock_timezone):
        activities = [
            (Job.JOB_STATE_NEW, '', self.created_ts('11:50')),
            (Job.JOB_STATE_AUTHORIZED, '', self.created_ts('11:58')),
            (Job.JOB_STATE_RUNNING, '', self.created_ts('11:59')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STAGING, self.created_ts('12:00')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_RUNNING, self.created_ts('12:30')),
            (Job.JOB_STATE_ERROR, Job.JOB_STEP_RUNNING, self.created_ts('13:15')),
        ]
        mock_job = self.mock_job(activities, num_cpus=32)
        usage = JobUsage(mock_job)
        mock_timezone.now.return_value = self.created_ts('14:30')
        self.assertEqual(usage.vm_hours, 1.25)

    @patch('data.jobusage.timezone')
    def test_vm_hours_skip_idle_time_while_in_error(self, mock_timezone):
        activities = [
            (Job.JOB_STATE_NEW, '', self.created_ts('11:50')),
            (Job.JOB_STATE_AUTHORIZED, '', self.created_ts('11:58')),
            (Job.JOB_STATE_RUNNING, '', self.created_ts('11:59')),
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STAGING, self.created_ts('12:00')),       # 2 min staging
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_RUNNING, self.created_ts('12:02')),       # 8 min running
            (Job.JOB_STATE_ERROR, Job.JOB_STEP_RUNNING, self.created_ts('12:10')),         # 60 min idle
            (Job.JOB_STATE_RESTARTING, Job.JOB_STEP_RUNNING, self.created_ts('13:10')),    # user clicks restart
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_RUNNING, self.created_ts('13:20')),       # 20 min running
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_STORE_OUTPUT, self.created_ts('13:40')),  # 5 min storing output
            (Job.JOB_STATE_RUNNING, Job.JOB_STEP_TERMINATE_VM, self.created_ts('13:45')),
            (Job.JOB_STATE_FINISHED, '', self.created_ts('12:50')),
        ]
        mock_job = self.mock_job(activities, num_cpus=32)
        usage = JobUsage(mock_job)
        mock_timezone.return_value = self.created_ts('14:30')
        self.assertEqual(usage.vm_hours * 60, 35)  # 2(staging) + 8(running) + 20(running) + 5(store output)