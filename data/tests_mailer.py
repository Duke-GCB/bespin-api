from django.test import TestCase
from data.mailer import EmailMessageFactory, EmailMessageSender, JobMailer, MailerConfig, MailerClient, EMAIL_EXCHANGE, \
    ROUTING_KEY
from data.models import EmailMessage, EmailTemplate, Job
from unittest.mock import MagicMock, patch, call, ANY
from data.exceptions import EmailServiceException, EmailAlreadySentException
from django.test.utils import override_settings


class EmailMessageFactoryTestCase(TestCase):

    def setUp(self):
        self.email_template = EmailTemplate.objects.create(
            name='template1',
            body_template='Body {{ field1 }}',
            subject_template='Subject {{ field2}}',
        )
        self.context = {
            'field1': 'abc',
            'field2': 'def'
        }
        self.sender_email = 'sender@example.com'
        self.to_email = 'recipient@university.edu'

    def test_makes_message(self):
        factory = EmailMessageFactory(self.email_template)

        message = factory.make_message(
            self.context,
            self.sender_email,
            self.to_email
        )

        self.assertEqual(message.body, 'Body abc')
        self.assertEqual(message.subject, 'Subject def')
        self.assertEqual(message.sender_email, self.sender_email)
        self.assertEqual(message.to_email, self.to_email)


class EmailMessageSenderTestCase(TestCase):

    def setUp(self):
        self.subject = 'Message Subject'
        self.body = 'Message Body'
        self.sender_email = 'sender@example.com'
        self.to_email = 'recipient@university.edu'

        self.email_message = EmailMessage.objects.create(
            body=self.body,
            subject=self.subject,
            sender_email=self.sender_email,
            to_email=self.to_email
        )

    @patch('data.mailer.DjangoEmailMessage')
    def test_sends_email(self, MockDjangoEmailMessage):
        mock_send = MagicMock()
        MockDjangoEmailMessage.return_value.send = mock_send
        sender = EmailMessageSender(self.email_message)
        sender.send()
        self.assertEqual(self.email_message.state, EmailMessage.MESSAGE_STATE_SENT)
        self.assertEqual(mock_send.call_count, 1)
        self.assertTrue(mock_send.call_args(self.subject, self.body, self.sender_email, [self.to_email],))

    @patch('data.mailer.DjangoEmailMessage')
    def test_captures_errors_on_send(self, MockDjangoEmailMessage):
        mock_send = MagicMock()
        mock_send.side_effect = Exception('Email error')
        MockDjangoEmailMessage.return_value.send = mock_send
        sender = EmailMessageSender(self.email_message)
        with self.assertRaises(EmailServiceException):
            sender.send()
        self.assertEqual(self.email_message.state, EmailMessage.MESSAGE_STATE_ERROR)
        self.assertEqual(self.email_message.errors, 'Email error')
        self.assertEqual(mock_send.call_count, 1)
        self.assertTrue(mock_send.call_args(self.subject, self.body, self.sender_email, [self.to_email],))

    def test_raises_if_already_sent(self):
        self.email_message.mark_sent()
        sender = EmailMessageSender(self.email_message)
        with self.assertRaises(EmailAlreadySentException):
            sender.send()

    @patch('data.mailer.DjangoEmailMessage')
    def test_splits_admin_bcc(self, MockDjangoEmailMessage):
        bcc_emails = ['bcc1@domain.com','bcc2@domain.com']
        self.email_message.bcc_email = ' '.join(bcc_emails)
        mock_send = MagicMock()
        MockDjangoEmailMessage.return_value.send = mock_send
        sender = EmailMessageSender(self.email_message)
        sender.send()
        self.assertEqual(self.email_message.state, EmailMessage.MESSAGE_STATE_SENT)
        self.assertEqual(mock_send.call_count, 1)
        self.assertTrue(mock_send.call_args(self.subject, self.body, self.sender_email, [self.to_email], bcc=[bcc_emails]))


FROM_EMAIL = 'sender@otherdomain.com'
ADMIN_BCC = ['admin-bcc@domain.com']

@override_settings(DEFAULT_FROM_EMAIL=FROM_EMAIL)
@override_settings(BESPIN_MAILER_ADMIN_BCC=ADMIN_BCC)
class JobMailerTestCase(TestCase):
    def setUp(self):
        EmailTemplate.objects.create(
            name='job-running-user',
            body_template='Started {{ name }}',
            subject_template ='Job {{ id }} has started'
        )
        EmailTemplate.objects.create(
            name='job-cancel-user',
            body_template='Canceled {{ name }}',
            subject_template ='Job {{ id }} has been canceled'
        )
        EmailTemplate.objects.create(
            name='job-finished-user',
            body_template='Finished {{ name }}',
            subject_template ='Job {{ id }} has completed'
        )
        EmailTemplate.objects.create(
            name='job-finished-sharegroup',
            body_template='Share Group: Finished {{ name }}',
            subject_template ='Share Group: Job {{ id }} has completed'
        )
        EmailTemplate.objects.create(
            name='job-error-user',
            body_template='Errored {{ name }}',
            subject_template ='Job {{ id }} has failed'
        )

    @patch('data.mailer.DjangoEmailMessage')
    def test_mails_running_job(self, MockSender):
        mock_send = MagicMock()
        MockSender.return_value.send = mock_send
        expected_body = 'Started TEST'
        expected_subject = 'Job 56 has started'
        expected_to_email = 'user@domain.com'
        expected_sender_email = FROM_EMAIL
        expected_bcc = ADMIN_BCC
        user = MagicMock(email=expected_to_email)
        job = MagicMock(state=Job.JOB_STATE_RUNNING, id=56, user=user)
        job.name = 'TEST'
        mailer = JobMailer(job, queue_messages=False)
        mailer.mail_current_state()
        self.assertTrue(MockSender.called)
        self.assertEqual(mock_send.call_count, 1)
        expected_calls = [
            call(expected_subject, expected_body, expected_sender_email, [expected_to_email], bcc=expected_bcc),
            call().send()
        ]
        self.assertEqual(MockSender.mock_calls, expected_calls)

    @patch('data.mailer.DjangoEmailMessage')
    def test_mails_canceled_job(self, MockSender):
        mock_send = MagicMock()
        MockSender.return_value.send = mock_send
        expected_body = 'Canceled TEST'
        expected_subject = 'Job 33 has been canceled'
        expected_to_email = 'user@domain.com'
        expected_sender_email = FROM_EMAIL
        expected_bcc = ADMIN_BCC
        user = MagicMock(email=expected_to_email)
        job = MagicMock(state=Job.JOB_STATE_CANCEL, id=33, user=user)
        job.name = 'TEST'
        mailer = JobMailer(job, queue_messages=False)
        mailer.mail_current_state()
        self.assertTrue(MockSender.called)
        self.assertEqual(mock_send.call_count, 1)
        expected_calls = [
            call(expected_subject, expected_body, expected_sender_email, [expected_to_email], bcc=expected_bcc),
            call().send()
        ]
        self.assertEqual(MockSender.mock_calls, expected_calls)

    @patch('data.mailer.DjangoEmailMessage')
    def test_mails_finished_job(self, MockSender):
        mock_send = MagicMock()
        MockSender.return_value.send = mock_send
        expected_user_body = 'Finished TEST'
        expected_user_subject = 'Job 66 has completed'
        expected_sharegroup_body = 'Share Group: Finished TEST'
        expected_sharegroup_subject = 'Share Group: Job 66 has completed'
        expected_user_email = 'user@domain.com'
        expected_sharegroup_email = 'sharegroup@domain.com'
        expected_sender_email = FROM_EMAIL
        expected_bcc = ADMIN_BCC
        user = MagicMock(email=expected_user_email)
        sharegroup = MagicMock(email=expected_sharegroup_email)
        job = MagicMock(state=Job.JOB_STATE_FINISHED, id=66, user=user, share_group=sharegroup)
        job.name = 'TEST'
        mailer = JobMailer(job, queue_messages=False)
        mailer.mail_current_state()
        self.assertTrue(MockSender.called)
        self.assertEqual(mock_send.call_count, 2)
        expected_calls = [
            call(expected_user_subject, expected_user_body, expected_sender_email, [expected_user_email], bcc=expected_bcc),
            call().send(),
            call(expected_sharegroup_subject, expected_sharegroup_body, expected_sender_email, [expected_sharegroup_email], bcc=expected_bcc),
            call().send(),
        ]
        self.assertEqual(MockSender.mock_calls, expected_calls)

    @patch('data.mailer.DjangoEmailMessage')
    def test_mails_errored_job(self, MockSender):
        mock_send = MagicMock()
        MockSender.return_value.send = mock_send
        expected_body = 'Errored TEST'
        expected_subject = 'Job 61 has failed'
        expected_to_email = 'user@domain.com'
        expected_sender_email = FROM_EMAIL
        expected_bcc = ADMIN_BCC
        user = MagicMock(email=expected_to_email)
        job = MagicMock(state=Job.JOB_STATE_ERROR, id=61, user=user)
        job.name = 'TEST'
        mailer = JobMailer(job, queue_messages=False)
        mailer.mail_current_state()
        self.assertTrue(MockSender.called)
        self.assertEqual(mock_send.call_count, 1)
        expected_calls = [
            call(expected_subject, expected_body, expected_sender_email, [expected_to_email], bcc=expected_bcc),
            call().send()
        ]
        self.assertEqual(MockSender.mock_calls, expected_calls)


class MailerConfigTestCase(TestCase):
    @patch('data.mailer.Job', autospec=True)
    def test_constructor(self, mock_job):
        mailer_config = MailerConfig(job_id=23)

        expected_lando_connection = mock_job.objects.get.return_value.job_settings.lando_connection
        self.assertEqual(mailer_config.work_queue_config, expected_lando_connection)
        mock_job.objects.get.assert_called_with(pk=23)


class MailerClientTestCase(TestCase):
    @patch('data.mailer.MailerConfig', autospec=True)
    @patch('data.mailer.WorkQueueConnection')  # autospec was unable to find connection property
    def test_send(self, mock_work_queue_connection, mock_mailer_config):
        client = MailerClient(job_id=23)
        client.send(send_email_id=45)

        mock_mailer_config.assert_called_with(23)
        mock_work_queue_connection.assert_called_with(mock_mailer_config.return_value)

        mock_channel = mock_work_queue_connection.return_value.connection.channel.return_value
        mock_channel.basic_publish.assert_called_with(exchange=EMAIL_EXCHANGE, routing_key=ROUTING_KEY, body=ANY)
