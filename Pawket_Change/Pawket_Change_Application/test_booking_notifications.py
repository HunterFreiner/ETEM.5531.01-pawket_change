from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Booking, BookingNotification, Pet
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

    def test_stay_receipt_matches_page_and_email(self):
        response = self.submit()
        booking = Booking.objects.get()
        self.assertEqual(booking.status, Booking.PENDING)
        notice = booking.notifications.get()
        self.assertEqual(notice.state, 'preview')
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['guest@example.com'])
        self.assertEqual(email.reply_to, ['help@example.com'])
        page = self.client.get(response.url)
        for value in ['Awaiting approval', booking.reference, 'Overnight Boarding', 'Biscuit',
                      '10:00 AM', '3:00 PM', 'America/Chicago', 'help@example.com', '$90']:
            self.assertIn(value, email.body)
            self.assertContains(page, value)
        self.assertContains(page, 'no email has been sent to your inbox')
        self.assertIn('no-store', page['Cache-Control'])

    def test_grooming_only_and_combined_details(self):
        data = payload(includes_stay='', grooming_services=['bath', 'nail_trimming'],
                       grooming_date=payload()['check_in_date'], grooming_time='11:00')
        response = self.submit(data)
        self.assertIn('Bath, Nail trimming', mail.outbox[0].body)
        self.assertIn('11:00 AM', mail.outbox[0].body)
        self.assertNotIn('Drop-off:', mail.outbox[0].body)
        self.assertContains(self.client.get(response.url), 'Preferred appointment')
        self.submit(payload(grooming_services=['haircut']))
        self.assertIn('During the requested stay', mail.outbox[1].body)
        self.assertIn('$130', mail.outbox[1].body)

    def test_duplicate_submission_and_refresh_send_once(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual(first.url, second.url)
        self.client.get(first.url)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Pet.objects.count(), 1)
        self.assertEqual(BookingNotification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_other_session_cannot_read_customer_data(self):
        response = self.submit()
        self.assertEqual(Client().get(response.url).status_code, 404)
        self.assertEqual(self.client.get(response.url).status_code, 200)

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
        notice = BookingNotification.objects.get()
        self.assertEqual(notice.state, 'failed')
        self.assertContains(self.client.get(response.url), 'could not send your email')
        call_command('retry_booking_notifications', stdout=StringIO())
        call_command('retry_booking_notifications', stdout=StringIO())
        notice.refresh_from_db()
        self.assertEqual(notice.attempts, 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Booking.objects.get().status, Booking.PENDING)

    def test_smtp_success_is_not_claimed_as_inbox_delivery(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
            with patch('Pawket_Change_Application.notifications.EmailMessage.send', return_value=1):
                response = self.submit()
        notice = BookingNotification.objects.get()
        self.assertEqual(notice.state, 'sent')
        self.assertIsNotNone(notice.sent_at)
        self.assertContains(self.client.get(response.url), 'accepted by our mail service')
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

    def test_html_input_is_escaped_on_confirmation(self):
        response = self.submit(payload(owner_name='<script>alert(1)</script>'))
        self.assertNotContains(self.client.get(response.url), '<script>alert(1)</script>')
        self.assertIn('<script>alert(1)</script>', mail.outbox[0].body)  # plain text email

    def test_admin_status_change_queues_confirmation_after_pet_save(self):
        self.submit()
        booking = Booking.objects.get()
        User.objects.create_superuser('admin', 'admin@example.com', 'test-only-password')
        self.client.login(username='admin', password='test-only-password')
        pet = booking.pets.get()
        data = {
            'owner_name': booking.owner_name, 'email': booking.email, 'phone': booking.phone,
            'number_of_pets': 1, 'status': 'confirmed', 'includes_stay': 'on',
            'check_in_date': booking.check_in_date.isoformat(), 'check_out_date': booking.check_out_date.isoformat(),
            'drop_off_time': '10:00:00', 'pickup_time': '15:00:00', 'grooming_services': '[]',
            'pets-TOTAL_FORMS': '1', 'pets-INITIAL_FORMS': '1', 'pets-MIN_NUM_FORMS': '0', 'pets-MAX_NUM_FORMS': '1000',
            'pets-0-id': pet.pk, 'pets-0-booking': booking.pk, 'pets-0-name': pet.name,
            'pets-0-breed': pet.breed, 'pets-0-size': pet.size, 'pets-0-age': pet.age, '_save': 'Save',
        }
        url = f'/admin/Pawket_Change_Application/booking/{booking.pk}/change/'
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.CONFIRMED)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Status: Confirmed', mail.outbox[-1].body)
        self.assertIn('Biscuit', mail.outbox[-1].body)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, data)
        self.assertEqual(len(mail.outbox), 2)
        page = self.client.get(reverse('booking_confirmation', args=[booking.pk]))
        self.assertContains(page, 'Your Booking Is Confirmed')
        self.assertNotContains(page, 'not confirmed yet')

    def test_old_failed_pending_email_is_not_retried_after_approval(self):
        with patch('Pawket_Change_Application.notifications.EmailMessage.send', side_effect=OSError):
            self.submit()
        booking = Booking.objects.get()
        booking.status = Booking.CONFIRMED
        booking.save(update_fields=['status'])
        call_command('retry_booking_notifications', stdout=StringIO())
        self.assertEqual(BookingNotification.objects.get().attempts, 1)
