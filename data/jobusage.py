from data.models import Job
import datetime
from django.utils import timezone

SECONDS_IN_AN_HOUR = 3600.0


class JobUsage(object):
    def __init__(self, job):
        self.job = job
        self.vm_hours = self._calculate_vm_hours()
        self.cpu_hours = self._calculate_cpu_hours(self.vm_hours)

    @staticmethod
    def _zip_job_activity_pairs(activities):
        """
        Return a list of (activity, next_activity) pairs based on this job's activities.
        Last next_activity value will be None.
        :param activities: [JobActivity]: activities to be zipped
        :return: [(JobActivity, JobActivity)]: pairs of job activities
        """
        return list(zip(activities, activities[1:] + [None]))

    def _filtered_activity_pairs(self, state, steps_to_include):
        """
        Return pairs(current_activity, next_activity) of this job's activities filtered by state and step data.
        :param state: str: the job state to include
        :param steps_to_include: [str]: list of job steps to include
        :return: [JobActivity]: pairs of job activities
        """
        filtered_activity_pairs = []
        activities = list(self.job.job_activities.order_by('created'))
        for activity_pair in self._zip_job_activity_pairs(activities):
            activity, next_activity = activity_pair
            if activity.state == state and activity.step in steps_to_include:
                filtered_activity_pairs.append(activity_pair)
        return filtered_activity_pairs

    @staticmethod
    def _calculate_elapsed_hours(activity, next_activity):
        """
        Return how long an activity took in hours.
        :param activity: JobActivity: activity to determine length of (starting time)
        :param next_activity: JobActivity: next activity (stopping time)
        :return: float: number of hours ellapsed in activity
        """
        if next_activity:
            end_datetime = next_activity.created
        else:
            end_datetime = timezone.now()
        time_delta = end_datetime - activity.created
        elapsed_seconds = time_delta.total_seconds()
        return elapsed_seconds / SECONDS_IN_AN_HOUR

    def _calculate_vm_hours(self):
        """
        Calculate how long a job has run(or is currently running) on a VM.
        :return: float: number hours
        """
        hours = 0
        steps_to_include = [Job.JOB_STEP_STAGING, Job.JOB_STEP_RUNNING, Job.JOB_STEP_STORE_OUTPUT]
        vm_step_activity_pairs = self._filtered_activity_pairs(Job.JOB_STATE_RUNNING, steps_to_include)
        for activity, next_activity in vm_step_activity_pairs:
            hours += self._calculate_elapsed_hours(activity, next_activity)
        return hours

    def _calculate_cpu_hours(self, vm_hours):
        """
        Calculate how many CPU hours a job has used up.
        :param vm_hours: int: number VM hours used by job
        :return: int
        """
        return vm_hours * self.job.job_flavor.cpus
