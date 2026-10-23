from datetime import datetime, time, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower

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

GROOMING_SERVICES = [
    ('bath', 'Bath'),
    ('haircut', 'Haircut'),
    ('nail_trimming', 'Nail trimming'),
    ('deshedding', 'Brush / deshedding'),
    ('ear_cleaning', 'Ear cleaning'),
]

GROOMING_PRICES = {
    'bath': 30,
    'haircut': 40,
    'nail_trimming': 12,
    'deshedding': 20,
    'ear_cleaning': 10,
}



class Booking(models.Model):
    email = models.EmailField()

    # Whether the customer is booking a stay
    includes_stay = models.BooleanField(default=True)

    # Existing stay booking fields
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)
    drop_off_time = models.TimeField(null=True, blank=True)
    pickup_time = models.TimeField(null=True, blank=True)

    # Grooming services selected by the customer
    grooming_services = models.JSONField(default=list, blank=True)

    # Used when booking grooming without a stay
    grooming_date = models.DateField(null=True, blank=True)
    grooming_time = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.includes_stay:
            return f'Booking {self.check_in_date} to {self.check_out_date}'
        return f'Grooming booking for {self.grooming_date}'

    @property
    def nights(self):
        if not self.includes_stay or not self.check_in_date or not self.check_out_date:
            return 0
        return (self.check_out_date - self.check_in_date).days

    @property
    def length_of_stay(self):
        if not self.includes_stay:
            return 'Grooming appointment'
        if self.nights == 0:
            return 'Same-day stay'
        return f'{self.nights} night{"s" if self.nights != 1 else ""}'

    @property
    def grooming_service_names(self):
        service_labels = dict(GROOMING_SERVICES)
        return [
            service_labels.get(service, service)
            for service in self.grooming_services
        ]

    @property
    def cost(self):
        """
        Calculate stay cost using existing pricing.
        Grooming pricing will be added separately.
        """
        if not self.includes_stay:
            return 0

        if not all([
            self.check_in_date,
            self.check_out_date,
            self.drop_off_time,
            self.pickup_time
        ]):
            return 0

        if self.nights > 0:
            return self.nights * OVERNIGHT_PRICE

        drop_off = datetime.combine(
            self.check_in_date,
            self.drop_off_time
        )
        pickup = datetime.combine(
            self.check_out_date,
            self.pickup_time
        )

        if pickup - drop_off <= timedelta(hours=HALF_DAY_MAX_HOURS):
            return HALF_DAY_PRICE

        return FULL_DAY_PRICE

    @property
    def grooming_cost(self):
        return sum(
            GROOMING_PRICES.get(service, 0)
            for service in self.grooming_services
        )

    @property
    def total_cost(self):
        return self.cost + self.grooming_cost



class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(max_length=2000)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Message from {self.name} ({self.email})'


class Review(models.Model):
    """Only someone with a booking under this email can leave a review; each email has one review, which it can edit."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(Lower('email'), name='one_review_per_email'),
        ]

    def __str__(self):
        return f'{self.rating}-star review from {self.name}'
