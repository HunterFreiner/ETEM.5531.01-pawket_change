from collections import defaultdict
from datetime import datetime, timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import (
    Booking, BUSINESS_HOURS, CLOSING_TIME, ContactMessage,
    GROOMING_PRICES, GROOMING_SERVICES, MAX_STAY_NIGHTS,
    OPENING_TIME, Review, SLOT_MINUTES,
)


def time_slots():
    """Every 15 minutes from opening to closing, e.g. ('08:00', '8:00 AM')."""
    slots = [('', 'Select a time')]
    current = datetime.combine(datetime.today(), OPENING_TIME)
    closing = datetime.combine(datetime.today(), CLOSING_TIME)
    while current <= closing:
        slots.append((current.strftime('%H:%M'), current.strftime('%I:%M %p').lstrip('0')))
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def booked_slots():
    slots = defaultdict(set)

    for booking in Booking.objects.filter(
        includes_stay=True,
        check_out_date__gte=timezone.localdate(),
        check_in_date__isnull=False,
        drop_off_time__isnull=False,
        pickup_time__isnull=False,
    ):
        slots[booking.check_in_date.isoformat()].add(
            booking.drop_off_time.strftime('%H:%M')
        )
        slots[booking.check_out_date.isoformat()].add(
            booking.pickup_time.strftime('%H:%M')
        )

    return {day: sorted(times) for day, times in slots.items()}


def slot_is_booked(day, time):
    return Booking.objects.filter(
        Q(check_in_date=day, drop_off_time=time) |
        Q(check_out_date=day, pickup_time=time),
        includes_stay=True,
    ).exists()



class BookingForm(forms.ModelForm):
    grooming_services = forms.MultipleChoiceField(
    choices=[
        (code, f'{name} — ${GROOMING_PRICES[code]}')
        for code, name in GROOMING_SERVICES
    ],
    widget=forms.CheckboxSelectMultiple,
    required=False,
    label='Grooming services',
)

    class Meta:
        model = Booking
        fields = [
            'email',
            'includes_stay',
            'grooming_services',
            'check_in_date',
            'drop_off_time',
            'check_out_date',
            'pickup_time',
            'grooming_date',
            'grooming_time',
        ]
        labels = {
            'email': 'Email address',
            'includes_stay': 'Include daycare or overnight stay',
            'check_in_date': 'Check-in / drop-off date',
            'drop_off_time': 'Drop-off time',
            'check_out_date': 'Check-out / pickup date',
            'pickup_time': 'Pickup time',
            'grooming_date': 'Preferred grooming date',
            'grooming_time': 'Preferred grooming time',
        }
        widgets = {
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'placeholder': 'you@example.com',
            }),
            'includes_stay': forms.CheckboxInput(),
            'check_in_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'check_out_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'drop_off_time': forms.Select(choices=time_slots()),
            'pickup_time': forms.Select(choices=time_slots()),
            'grooming_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'grooming_time': forms.Select(choices=time_slots()),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        today = timezone.localdate().isoformat()

        for field in [
            'check_in_date',
            'check_out_date',
            'grooming_date',
        ]:
            self.fields[field].widget.attrs['min'] = today

        # Stay fields are required only when a stay is selected.
        for field in [
            'check_in_date',
            'check_out_date',
            'drop_off_time',
            'pickup_time',
            'grooming_date',
            'grooming_time',
        ]:
            self.fields[field].required = False

        # New bookings default to a stay, like the original form.
        if not self.is_bound and self.instance.pk is None:
            self.initial['includes_stay'] = True

    def clean(self):
        cleaned = super().clean()

        includes_stay = cleaned.get('includes_stay')
        grooming = cleaned.get('grooming_services') or []

        check_in = cleaned.get('check_in_date')
        check_out = cleaned.get('check_out_date')
        drop_off = cleaned.get('drop_off_time')
        pickup = cleaned.get('pickup_time')

        grooming_date = cleaned.get('grooming_date')
        grooming_time = cleaned.get('grooming_time')

        # At least one service must be selected.
        if not includes_stay and not grooming:
            raise forms.ValidationError(
                'Please select a stay, grooming services, or both.'
            )

        def validate_time(field, value):
            if value is None:
                return

            if not OPENING_TIME <= value <= CLOSING_TIME:
                self.add_error(
                    field,
                    f'Please choose a time during business hours ({BUSINESS_HOURS}).'
                )
            elif value.minute % SLOT_MINUTES or value.second:
                self.add_error(
                    field,
                    f'Please choose a time in {SLOT_MINUTES}-minute increments.'
                )

        now = timezone.localtime()
        today = timezone.localdate()

        if includes_stay:
            for field in [
                'check_in_date',
                'check_out_date',
                'drop_off_time',
                'pickup_time',
            ]:
                if not cleaned.get(field):
                    self.add_error(field, 'This field is required for a stay.')

            if check_in and check_in < today:
                self.add_error(
                    'check_in_date',
                    'Check-in date cannot be in the past.'
                )

            if check_in and check_out:
                if check_out < check_in:
                    self.add_error(
                        'check_out_date',
                        'Check-out cannot be before check-in.'
                    )
                elif (check_out - check_in).days > MAX_STAY_NIGHTS:
                    self.add_error(
                        'check_out_date',
                        f'Stays can be at most {MAX_STAY_NIGHTS} nights.'
                    )
                elif (
                    check_out == check_in
                    and drop_off
                    and pickup
                    and pickup <= drop_off
                ):
                    self.add_error(
                        'pickup_time',
                        'Pickup must be after drop-off for same-day stays.'
                    )

            validate_time('drop_off_time', drop_off)
            validate_time('pickup_time', pickup)

            if check_in == today and drop_off and drop_off <= now.time():
                self.add_error(
                    'drop_off_time',
                    'That drop-off time has already passed.'
                )

            if check_in and drop_off and slot_is_booked(check_in, drop_off):
                self.add_error(
                    'drop_off_time',
                    'That drop-off slot is already booked.'
                )

            if check_out and pickup and slot_is_booked(check_out, pickup):
                self.add_error(
                    'pickup_time',
                    'That pickup slot is already booked.'
                )

            # Grooming is performed during the stay.
            cleaned['grooming_date'] = None
            cleaned['grooming_time'] = None

        else:
            # Grooming-only bookings don't require stay details.
            for field in [
                'check_in_date',
                'check_out_date',
                'drop_off_time',
                'pickup_time',
            ]:
                cleaned[field] = None

            if not grooming_date:
                self.add_error(
                    'grooming_date',
                    'Please select a grooming appointment date.'
                )

            if not grooming_time:
                self.add_error(
                    'grooming_time',
                    'Please select a grooming appointment time.'
                )

            if grooming_date and grooming_date < today:
                self.add_error(
                    'grooming_date',
                    'Grooming date cannot be in the past.'
                )

            validate_time('grooming_time', grooming_time)

            if (
                grooming_date == today
                and grooming_time
                and grooming_time <= now.time()
            ):
                self.add_error(
                    'grooming_time',
                    'That appointment time has already passed.'
                )

        return cleaned



class ContactForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            for field_name in self.errors:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'aria-invalid': 'true',
                        'aria-describedby': f'id_{field_name}-error',
                    })

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'message']
        labels = {
            'name': 'Name',
            'email': 'Email address',
            'message': 'How can we help?',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'autocomplete': 'name',
                'class': 'form-control',
                'placeholder': 'Your name',
            }),
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'class': 'form-control',
                'placeholder': 'you@example.com',
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Tell us what you need help with',
                'rows': 6,
            }),
        }


class ReviewEmailForm(forms.Form):
    email = forms.EmailField(
        label='Email used for your booking',
        # No autocomplete, so the browser does not suggest other people's emails on a shared device.
        widget=forms.EmailInput(attrs={'autocomplete': 'off', 'placeholder': 'you@example.com'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if not Booking.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'We could not find a booking with that email. Only guests who have booked a stay can leave a review.'
            )
        return email


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['name', 'rating', 'comment']
        labels = {
            'name': 'Name shown with your review',
            'rating': 'Rating',
            'comment': 'Your review',
        }
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'e.g. Jordan P.'}),
            'rating': forms.Select(choices=[('', 'Select a rating')] + [(n, f'{n} star{"s" if n != 1 else ""}') for n in range(5, 0, -1)]),
            'comment': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Tell other pet owners about your stay'}),
        }
