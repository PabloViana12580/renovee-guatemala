"""Email notifications: one-line subjects, no recipients means no email, and a mail outage is not an error."""

from unittest import mock

from django.core import mail
from django.test import SimpleTestCase

from core.notifications import send_notification, single_line


@mock.patch('core.notifications.render_to_string', return_value='Message body')
class NotificationTests(SimpleTestCase):
    def notify(self, to):
        return send_notification(subject='New message\nBcc: someone@example.com', template='any.txt', context={}, to=to)

    def test_email_is_sent_with_a_single_line_subject(self, render):
        self.assertTrue(self.notify(['owner@example.com', '']))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])
        self.assertEqual(mail.outbox[0].subject, 'New message Bcc: someone@example.com')
        self.assertEqual(mail.outbox[0].body, 'Message body')

    def test_without_recipients_nothing_is_sent(self, render):
        self.assertFalse(self.notify(['']))
        self.assertEqual(mail.outbox, [])

    def test_mail_outage_is_logged_not_raised(self, render):
        with mock.patch('core.notifications.send_mail', side_effect=OSError('connection refused')):
            with self.assertLogs('core.notifications', level='ERROR') as logs:
                self.assertFalse(self.notify(['owner@example.com']))
        self.assertIn('email.failed', logs.output[0])

    def test_single_line_limits_length(self, render):
        self.assertEqual(single_line('a  b\r\nc', limit=4), 'a b ')
