from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from .models import Booking, BUSINESS_HOURS, CLOSING_TIME, MAX_STAY_NIGHTS, OPENING_TIME


def time_slots():
    """Every 30 minutes from opening to closing, e.g. ('08:00', '8:00 AM')."""
    slots = [('', 'Select a time')]
    current = datetime.combine(datetime.today(), OPENING_TIME)
    closing = datetime.combine(datetime.today(), CLOSING_TIME)
    while current <= closing:
        slots.append((current.strftime('%H:%M'), current.strftime('%I:%M %p').lstrip('0')))
        current += timedelta(minutes=30)
    return slots


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['check_in_date', 'pickup_time', 'check_out_date', 'drop_off_time']
        labels = {
            'check_in_date': 'Check-in / pickup date',
            'pickup_time': 'Pickup time',
            'check_out_date': 'Check-out / drop-off date',
            'drop_off_time': 'Drop-off time',
        }
        widgets = {
            'check_in_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'check_out_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'pickup_time': forms.Select(choices=time_slots()),
            'drop_off_time': forms.Select(choices=time_slots()),
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
        return value

    def clean_pickup_time(self):
        return self._clean_business_hours('pickup_time')

    def clean_drop_off_time(self):
        return self._clean_business_hours('drop_off_time')

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_date')
        check_out = cleaned_data.get('check_out_date')
        pickup = cleaned_data.get('pickup_time')
        drop_off = cleaned_data.get('drop_off_time')

        if check_in and check_out:
            if check_out < check_in:
                self.add_error('check_out_date', 'Check-out date cannot be before the check-in date.')
            elif (check_out - check_in).days > MAX_STAY_NIGHTS:
                self.add_error('check_out_date', f'Stays can be at most {MAX_STAY_NIGHTS} nights.')
            elif check_out == check_in and pickup and drop_off and drop_off <= pickup:
                self.add_error('drop_off_time', 'For a same-day stay, drop-off must be after pickup.')

        now = timezone.localtime()
        if check_in == now.date() and pickup and pickup <= now.time():
            self.add_error('pickup_time', 'That pickup time has already passed today.')

        return cleaned_data
