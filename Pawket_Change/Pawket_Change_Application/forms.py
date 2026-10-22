from collections import defaultdict
from datetime import datetime, timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Booking, BUSINESS_HOURS, CLOSING_TIME, MAX_STAY_NIGHTS, OPENING_TIME, SLOT_MINUTES


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
    """Drop-off and pickup times already taken on each upcoming date, e.g. {'2026-10-20': ['08:00', '14:15']}."""
    slots = defaultdict(set)
    for booking in Booking.objects.filter(check_out_date__gte=timezone.localdate()):
        slots[booking.check_in_date.isoformat()].add(booking.drop_off_time.strftime('%H:%M'))
        slots[booking.check_out_date.isoformat()].add(booking.pickup_time.strftime('%H:%M'))
    return {day: sorted(times) for day, times in slots.items()}


def slot_is_booked(day, time):
    """Only one drop-off or pickup can happen in each time slot on a given day."""
    return Booking.objects.filter(
        Q(check_in_date=day, drop_off_time=time) | Q(check_out_date=day, pickup_time=time)
    ).exists()


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['check_in_date', 'drop_off_time', 'check_out_date', 'pickup_time']
        labels = {
            'check_in_date': 'Check-in / drop-off date',
            'drop_off_time': 'Drop-off time',
            'check_out_date': 'Check-out / pickup date',
            'pickup_time': 'Pickup time',
        }
        widgets = {
            'check_in_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'check_out_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'drop_off_time': forms.Select(choices=time_slots()),
            'pickup_time': forms.Select(choices=time_slots()),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate().isoformat()
        self.fields['check_in_date'].widget.attrs['min'] = today
        self.fields['check_out_date'].widget.attrs['min'] = today

    def clean_check_in_date(self):
        check_in = self.cleaned_data['check_in_date']
        if check_in < timezone.localdate():
            raise forms.ValidationError('Check-in date cannot be in the past.')
        return check_in

    def _clean_business_hours(self, field):
        value = self.cleaned_data[field]
        if not OPENING_TIME <= value <= CLOSING_TIME:
            raise forms.ValidationError(f'Please choose a time during our business hours ({BUSINESS_HOURS}).')
        if value.minute % SLOT_MINUTES or value.second:
            raise forms.ValidationError(f'Please choose a time in {SLOT_MINUTES}-minute increments.')
        return value

    def clean_drop_off_time(self):
        return self._clean_business_hours('drop_off_time')

    def clean_pickup_time(self):
        return self._clean_business_hours('pickup_time')

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_date')
        check_out = cleaned_data.get('check_out_date')
        drop_off = cleaned_data.get('drop_off_time')
        pickup = cleaned_data.get('pickup_time')

        if check_in and check_out:
            if check_out < check_in:
                self.add_error('check_out_date', 'Check-out date cannot be before the check-in date.')
            elif (check_out - check_in).days > MAX_STAY_NIGHTS:
                self.add_error('check_out_date', f'Stays can be at most {MAX_STAY_NIGHTS} nights.')
            elif check_out == check_in and drop_off and pickup and pickup <= drop_off:
                self.add_error('pickup_time', 'For a same-day stay, pickup must be after drop-off.')

        now = timezone.localtime()
        if check_in == now.date() and drop_off and drop_off <= now.time():
            self.add_error('drop_off_time', 'That drop-off time has already passed today.')

        if check_in and drop_off and slot_is_booked(check_in, drop_off):
            self.add_error('drop_off_time', 'That drop-off time is already booked on this date. Please choose another time.')
        if check_out and pickup and slot_is_booked(check_out, pickup):
            self.add_error('pickup_time', 'That pickup time is already booked on this date. Please choose another time.')

        return cleaned_data


# Customer review submission form
from .models import Testimonial


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = [
            'customer_name',
            'pet_name',
            'rating',
            'review_text',
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your name',
            }),
            'pet_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Your pet's name",
            }),
            'rating': forms.Select(attrs={
                'class': 'form-select',
            }),
            'review_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about your experience...',
            }),
        }
