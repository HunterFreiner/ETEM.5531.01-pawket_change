from datetime import time

from django.db import models

# Pawket Change is open Monday-Sunday, 8:00 AM - 6:00 PM; pickups and drop-offs must fall within these hours.
OPENING_TIME = time(8, 0)
CLOSING_TIME = time(18, 0)
MAX_STAY_NIGHTS = 30
SLOT_MINUTES = 15
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
