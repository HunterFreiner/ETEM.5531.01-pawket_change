from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import BookingForm
from .models import Booking


def booking_data(check_in_offset=1, check_out_offset=3, drop_off='10:00', pickup='15:00'):
    today = timezone.localdate()
    return {
        'check_in_date': (today + timedelta(days=check_in_offset)).isoformat(),
        'check_out_date': (today + timedelta(days=check_out_offset)).isoformat(),
        'drop_off_time': drop_off,
        'pickup_time': pickup,
    }


class BookingFormTests(TestCase):
    def test_valid_booking(self):
        self.assertTrue(BookingForm(booking_data()).is_valid())

    def test_check_in_in_past_is_invalid(self):
        form = BookingForm(booking_data(check_in_offset=-1))
        self.assertIn('check_in_date', form.errors)

    def test_check_out_before_check_in_is_invalid(self):
        form = BookingForm(booking_data(check_in_offset=5, check_out_offset=2))
        self.assertIn('check_out_date', form.errors)

    def test_stay_longer_than_max_is_invalid(self):
        form = BookingForm(booking_data(check_out_offset=40))
        self.assertIn('check_out_date', form.errors)

    def test_same_day_pickup_before_drop_off_is_invalid(self):
        form = BookingForm(booking_data(check_out_offset=1, drop_off='14:00', pickup='11:00'))
        self.assertIn('pickup_time', form.errors)

    def test_same_day_pickup_after_drop_off_is_valid(self):
        form = BookingForm(booking_data(check_out_offset=1, drop_off='10:00', pickup='16:00'))
        self.assertTrue(form.is_valid())

    def test_times_outside_business_hours_are_invalid(self):
        form = BookingForm(booking_data(drop_off='07:30', pickup='18:30'))
        self.assertIn('pickup_time', form.errors)
        self.assertIn('drop_off_time', form.errors)

    def test_opening_and_closing_times_are_valid(self):
        self.assertTrue(BookingForm(booking_data(drop_off='08:00', pickup='18:00')).is_valid())


class BookingViewTests(TestCase):
    def test_booking_page_loads(self):
        response = self.client.get(reverse('book'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pickup time')
        self.assertContains(response, 'Monday–Sunday, 8:00 AM – 6:00 PM')

    def test_review_shows_details_without_saving(self):
        response = self.client.post(reverse('book'), {**booking_data(), 'action': 'review'})
        self.assertTemplateUsed(response, 'booking_review.html')
        self.assertContains(response, '2 nights')
        self.assertContains(response, '10:00 AM')
        self.assertEqual(Booking.objects.count(), 0)

    def test_invalid_booking_returns_to_form(self):
        response = self.client.post(reverse('book'), {**booking_data(check_in_offset=-1), 'action': 'review'})
        self.assertTemplateUsed(response, 'booking.html')
        self.assertEqual(Booking.objects.count(), 0)

    def test_edit_returns_to_form_with_values(self):
        response = self.client.post(reverse('book'), {**booking_data(), 'action': 'edit'})
        self.assertTemplateUsed(response, 'booking.html')
        self.assertContains(response, booking_data()['check_in_date'])

    def test_confirm_saves_booking(self):
        response = self.client.post(reverse('book'), {**booking_data(), 'action': 'confirm'})
        booking = Booking.objects.get()
        self.assertRedirects(response, reverse('booking_confirmation', args=[booking.id]))
