from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import BookingForm, ContactForm, time_slots
from .models import Booking, ContactMessage, Review


def booking_data(check_in_offset=1, check_out_offset=3, drop_off='10:00', pickup='15:00'):
    today = timezone.localdate()
    return {
        'email': 'guest@example.com',
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

    def test_email_is_required(self):
        form = BookingForm({**booking_data(), 'email': ''})
        self.assertIn('email', form.errors)

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


class ContactFormTests(TestCase):
    def test_valid_contact_message(self):
        form = ContactForm({
            'name': 'Dez Calloway',
            'email': 'dez@example.com',
            'message': 'Can you tell me whether next Saturday is available?',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_email_is_rejected(self):
        form = ContactForm({
            'name': 'Dez Calloway',
            'email': 'not-an-email',
            'message': 'I have a question.',
        })
        self.assertIn('email', form.errors)

    def test_all_fields_are_required(self):
        form = ContactForm({})
        self.assertEqual(set(form.errors), {'name', 'email', 'message'})


class ContactViewTests(TestCase):
    def valid_message(self):
        return {
            'name': 'Dez Calloway',
            'email': 'dez@example.com',
            'message': 'Can you tell me whether next Saturday is available?',
        }

    def test_contact_page_loads_with_team_provided_details_and_hours(self):
        response = self.client.get(reverse('contact'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Monday–Sunday, 8:00 AM – 6:00 PM')
        self.assertContains(response, '<a href="tel:314-555-0142">314-555-0142</a>', html=True)
        self.assertContains(response, '<a href="mailto:hello@pawketchange.org">hello@pawketchange.org</a>', html=True)
        self.assertContains(response, '100 Treat Street, St. Louis, MO 63101')
        self.assertNotContains(response, 'Not published yet')
        self.assertNotContains(response, 'We are still confirming our public business contact details.')
        self.assertContains(response, 'All fields are required.')

    @override_settings(
        CONTACT_PHONE='(555) 010-0200',
        CONTACT_EMAIL='hello@example.com',
        CONTACT_ADDRESS='123 Example Street',
    )
    def test_confirmed_contact_details_are_displayed(self):
        response = self.client.get(reverse('contact'))
        self.assertContains(response, '(555) 010-0200')
        self.assertContains(response, 'hello@example.com')
        self.assertContains(response, '123 Example Street')
        self.assertNotContains(response, 'Not published yet')

    def test_valid_submission_is_saved_before_success_is_shown(self):
        response = self.client.post(reverse('contact'), self.valid_message(), follow=True)
        self.assertRedirects(response, reverse('contact'))
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertContains(response, 'We received your message')

    def test_invalid_submission_is_not_saved(self):
        data = {**self.valid_message(), 'email': 'not-an-email'}
        response = self.client.post(reverse('contact'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertContains(response, 'Enter a valid email address')
        self.assertNotContains(response, 'We received your message')

    @patch('Pawket_Change_Application.views.ContactForm.save', side_effect=DatabaseError)
    def test_save_failure_shows_error_without_success(self, mocked_save):
        response = self.client.post(reverse('contact'), self.valid_message())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertContains(response, 'We could not send your message right now')
        self.assertNotContains(response, 'We received your message')

    def test_only_navigation_links_to_contact_page_from_home(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{reverse("contact")}"', count=1)


class ReviewViewTests(TestCase):
    def setUp(self):
        BookingForm(booking_data()).save()

    def verify(self, email):
        return self.client.post(reverse('reviews'), {'action': 'verify', 'email': email}, follow=True)

    def valid_review(self):
        return {'action': 'submit', 'name': 'Riley G.', 'rating': '5', 'comment': 'Wonderful stay!'}

    def test_reviews_page_shows_sample_reviews(self):
        response = self.client.get(reverse('reviews'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maya R.')
        self.assertNotContains(response, 'maya.sample@example.com')

    def test_navigation_links_to_reviews(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{reverse("reviews")}"')

    def test_review_email_field_has_autocomplete_off(self):
        response = self.client.get(reverse('reviews'))
        self.assertContains(response, 'autocomplete="off"')

    def test_unknown_email_cannot_leave_review(self):
        response = self.verify('stranger@example.com')
        self.assertContains(response, 'We could not find a booking with that email')
        self.assertNotContains(response, 'Post review')

    def test_review_without_verifying_is_not_saved(self):
        count = Review.objects.count()
        self.client.post(reverse('reviews'), self.valid_review())
        self.assertEqual(Review.objects.count(), count)

    def test_booked_email_can_leave_review(self):
        response = self.verify('GUEST@example.com')
        self.assertContains(response, 'Post review')
        response = self.client.post(reverse('reviews'), self.valid_review(), follow=True)
        review = Review.objects.get(name='Riley G.')
        self.assertEqual(review.email, 'GUEST@example.com')
        self.assertContains(response, 'Thanks for your review')
        self.assertContains(response, 'Wonderful stay!')

    def test_rating_must_be_between_one_and_five(self):
        self.verify('guest@example.com')
        response = self.client.post(reverse('reviews'), {**self.valid_review(), 'rating': '6'})
        self.assertFalse(Review.objects.filter(name='Riley G.').exists())
        self.assertContains(response, 'Post review')

    def test_email_that_already_reviewed_edits_existing_review(self):
        Review.objects.create(name='Riley G.', email='guest@example.com', rating=3, comment='Pretty good.')
        response = self.verify('Guest@Example.com')
        self.assertContains(response, 'Edit your review')
        self.assertContains(response, 'Pretty good.')
        response = self.client.post(reverse('reviews'), {**self.valid_review(), 'comment': 'Even better the second time!'}, follow=True)
        review = Review.objects.get(email='guest@example.com')
        self.assertEqual(review.comment, 'Even better the second time!')
        self.assertEqual(review.rating, 5)
        self.assertIsNotNone(review.edited_at)
        self.assertContains(response, 'Your review has been updated')
        self.assertContains(response, 'Edited')

    def test_review_posted_from_another_tab_is_edited_not_duplicated(self):
        self.verify('guest@example.com')
        Review.objects.create(name='Riley G.', email='GUEST@example.com', rating=5, comment='Posted from another tab')
        self.client.post(reverse('reviews'), {**self.valid_review(), 'comment': 'Second try'})
        self.assertEqual(Review.objects.filter(email__iexact='guest@example.com').count(), 1)
        self.assertEqual(Review.objects.get(email__iexact='guest@example.com').comment, 'Second try')

    def test_new_review_is_not_marked_edited(self):
        self.verify('guest@example.com')
        response = self.client.post(reverse('reviews'), self.valid_review(), follow=True)
        self.assertIsNone(Review.objects.get(name='Riley G.').edited_at)
        self.assertNotContains(response, 'Edited')

    def test_verified_email_can_delete_its_review(self):
        Review.objects.create(name='Riley G.', email='guest@example.com', rating=3, comment='Pretty good.')
        response = self.verify('guest@example.com')
        self.assertContains(response, 'Delete review')
        response = self.client.post(reverse('reviews'), {'action': 'delete'}, follow=True)
        self.assertFalse(Review.objects.filter(email='guest@example.com').exists())
        self.assertContains(response, 'Your review has been deleted')
        self.assertNotContains(response, 'Pretty good.')

    def test_delete_without_verifying_does_nothing(self):
        Review.objects.create(name='Riley G.', email='guest@example.com', rating=3, comment='Pretty good.')
        self.client.post(reverse('reviews'), {'action': 'delete'})
        self.assertTrue(Review.objects.filter(email='guest@example.com').exists())

    def test_new_reviewer_does_not_see_delete_button(self):
        response = self.verify('guest@example.com')
        self.assertNotContains(response, 'Delete review')

    def test_can_review_again_after_deleting(self):
        Review.objects.create(name='Riley G.', email='guest@example.com', rating=3, comment='Pretty good.')
        self.verify('guest@example.com')
        self.client.post(reverse('reviews'), {'action': 'delete'})
        response = self.verify('guest@example.com')
        self.assertContains(response, 'Leave a review')
        self.client.post(reverse('reviews'), self.valid_review())
        self.assertEqual(Review.objects.get(email='guest@example.com').comment, 'Wonderful stay!')

    def test_change_email_returns_to_email_step(self):
        self.verify('guest@example.com')
        response = self.client.post(reverse('reviews'), {'action': 'change_email'}, follow=True)
        self.assertContains(response, 'Continue')
        self.assertNotContains(response, 'Post review')
