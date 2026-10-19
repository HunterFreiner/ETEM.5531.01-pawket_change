from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import BookingForm, time_slots
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

    def test_time_slots_are_15_minutes_apart(self):
        values = [value for value, label in time_slots() if value]
        self.assertEqual(values[:3], ['08:00', '08:15', '08:30'])
        self.assertEqual(values[-1], '18:00')

    def test_time_not_on_15_minute_slot_is_invalid(self):
        form = BookingForm(booking_data(drop_off='08:10'))
        self.assertIn('drop_off_time', form.errors)


class BookedSlotTests(TestCase):
    def setUp(self):
        BookingForm(booking_data(drop_off='08:00', pickup='15:00')).save()

    def test_booked_drop_off_time_is_unavailable(self):
        form = BookingForm(booking_data(check_out_offset=5, drop_off='08:00', pickup='12:00'))
        self.assertIn('drop_off_time', form.errors)

    def test_booked_pickup_time_is_unavailable(self):
        form = BookingForm(booking_data(check_in_offset=3, check_out_offset=4, drop_off='15:00', pickup='12:00'))
        self.assertIn('drop_off_time', form.errors)

    def test_booked_time_is_available_on_other_dates(self):
        form = BookingForm(booking_data(check_in_offset=2, check_out_offset=4, drop_off='08:00', pickup='15:00'))
        self.assertTrue(form.is_valid())

    def test_booking_page_lists_booked_times(self):
        response = self.client.get(reverse('book'))
        booked = response.context['availability']['booked']
        self.assertEqual(booked[booking_data()['check_in_date']], ['08:00'])
        self.assertEqual(booked[booking_data()['check_out_date']], ['15:00'])


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

    def test_confirmation_shows_received_and_cost(self):
        self.client.post(reverse('book'), {**booking_data(), 'action': 'confirm'})
        response = self.client.get(reverse('booking_confirmation', args=[Booking.objects.get().id]))
        self.assertContains(response, 'has been received')
        self.assertContains(response, 'The cost for the stay will be <strong>$90</strong>')

    def test_review_shows_cost(self):
        response = self.client.post(reverse('book'), {**booking_data(), 'action': 'review'})
        self.assertContains(response, '$90')


class BookingCostTests(TestCase):
    def cost(self, **kwargs):
        form = BookingForm(booking_data(**kwargs))
        self.assertTrue(form.is_valid(), form.errors)
        return form.instance.cost

    def test_overnight_stay_is_charged_per_night(self):
        self.assertEqual(self.cost(check_out_offset=4), 3 * 45)

    def test_same_day_up_to_four_hours_is_half_day(self):
        self.assertEqual(self.cost(check_out_offset=1, drop_off='08:00', pickup='12:00'), 15)

    def test_same_day_over_four_hours_is_full_day(self):
        self.assertEqual(self.cost(check_out_offset=1, drop_off='08:00', pickup='12:15'), 25)
