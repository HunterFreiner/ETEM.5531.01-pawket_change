from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Booking, BookingNotification
from .notifications import deliver_booking_notification, queue_booking_notification


def payload(**changes):
    today = timezone.localdate()
    data = {
        'owner_name': 'Test Owner', 'email': 'guest@example.com', 'phone': '3145550142',
        'number_of_pets': '1', 'pet0-name': 'Biscuit', 'pet0-breed': 'Beagle',
        'pet0-size': 'medium', 'pet0-age': '3', 'includes_stay': 'on',
        'check_in_date': (today + timedelta(days=3)).isoformat(),
        'check_out_date': (today + timedelta(days=5)).isoformat(),
        'drop_off_time': '10:00', 'pickup_time': '15:00', 'action': 'confirm',
    }
    data.update(changes)
    return data


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='bookings@example.com', CONTACT_EMAIL='help@example.com',
                   CONTACT_PHONE='3145550100')
class BookingNotificationTests(TestCase):
    def submit(self, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('book'), data or payload())
        return response

    def test_stay_request_sends_receipt_email(self):
        self.submit()
        booking = Booking.objects.get()
        notice = booking.notifications.get()
        self.assertEqual(notice.state, 'preview')
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['guest@example.com'])
        self.assertEqual(email.reply_to, ['help@example.com'])
        self.assertIn(booking.reference, email.subject)
        for value in [booking.reference, 'Overnight Boarding', 'Biscuit', '10:00 AM', '3:00 PM',
                      'America/Chicago', 'help@example.com', '$90']:
            self.assertIn(value, email.body)

    def test_grooming_only_and_combined_details(self):
        data = payload(includes_stay='', grooming_services=['bath', 'nail_trimming'],
                       grooming_date=payload()['check_in_date'], grooming_time='11:00')
        self.submit(data)
        self.assertIn('Bath, Nail trimming', mail.outbox[0].body)
        self.assertIn('11:00 AM', mail.outbox[0].body)
        self.assertNotIn('Drop-off:', mail.outbox[0].body)
        self.submit(payload(grooming_services=['haircut']))
        self.assertIn('During the requested stay', mail.outbox[1].body)
        self.assertIn('$130', mail.outbox[1].body)

    def test_invalid_booking_does_not_queue_email(self):
        self.submit(payload(email='bad'))
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(BookingNotification.objects.exists())

    def test_rollback_does_not_send_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    booking = Booking.objects.create(email='guest@example.com')
                    queue_booking_notification(booking)
                    raise ValueError('Rollback test')
            except ValueError:
                pass
        self.assertFalse(BookingNotification.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_failure_keeps_booking_and_retry_does_not_duplicate(self):
        with patch('Pawket_Change_Application.notifications.EmailMessage.send', side_effect=OSError('offline')):
            response = self.submit()
        self.assertEqual(self.client.get(response.url).status_code, 200)
        notice = BookingNotification.objects.get()
        self.assertEqual(notice.state, 'failed')
        call_command('retry_booking_notifications', stdout=StringIO())
        call_command('retry_booking_notifications', stdout=StringIO())
        notice.refresh_from_db()
        self.assertEqual(notice.attempts, 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_success_is_not_claimed_as_inbox_delivery(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
            with patch('Pawket_Change_Application.notifications.EmailMessage.send', return_value=1):
                self.submit()
        notice = BookingNotification.objects.get()
        self.assertEqual(notice.state, 'sent')
        self.assertIsNotNone(notice.sent_at)
        self.assertFalse(deliver_booking_notification(notice.pk))

    def test_zero_backend_result_is_failure(self):
        with patch('Pawket_Change_Application.notifications.EmailMessage.send', return_value=0):
            self.submit()
        self.assertEqual(BookingNotification.objects.get().state, 'failed')

    def test_missing_sender_is_not_a_false_success(self):
        with override_settings(DEFAULT_FROM_EMAIL=''):
            self.submit()
        self.assertEqual(BookingNotification.objects.get().state, 'failed')
        self.assertEqual(len(mail.outbox), 0)

    def test_plain_text_email_is_not_html_escaped(self):
        self.submit(payload(owner_name='<script>alert(1)</script>'))
        self.assertIn('<script>alert(1)</script>', mail.outbox[0].body)
