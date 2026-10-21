from datetime import datetime, time, timedelta

from django.db import models

# Pawket Change is open Monday-Sunday, 8:00 AM - 6:00 PM; pickups and drop-offs must fall within these hours.
OPENING_TIME = time(8, 0)
CLOSING_TIME = time(18, 0)
MAX_STAY_NIGHTS = 30
SLOT_MINUTES = 15

# Prices shown on the Services page and used to calculate the cost of a stay.
FULL_DAY_PRICE = 25
HALF_DAY_PRICE = 15
HALF_DAY_MAX_HOURS = 4
OVERNIGHT_PRICE = 45
BUSINESS_HOURS = 'Monday–Sunday, 8:00 AM – 6:00 PM'


class Booking(models.Model):
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    drop_off_time = models.TimeField()
    pickup_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Booking {self.check_in_date} to {self.check_out_date}'

    @property
    def nights(self):
        return (self.check_out_date - self.check_in_date).days

    @property
    def length_of_stay(self):
        if self.nights == 0:
            return 'Same-day stay'
        return f'{self.nights} night{"s" if self.nights != 1 else ""}'

    @property
    def cost(self):
        """Overnight stays are charged per night; same-day stays are half-day or full-day daycare."""
        if self.nights > 0:
            return self.nights * OVERNIGHT_PRICE
        drop_off = datetime.combine(self.check_in_date, self.drop_off_time)
        pickup = datetime.combine(self.check_out_date, self.pickup_time)
        if pickup - drop_off <= timedelta(hours=HALF_DAY_MAX_HOURS):
            return HALF_DAY_PRICE
        return FULL_DAY_PRICE


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(max_length=2000)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Message from {self.name} ({self.email})'
