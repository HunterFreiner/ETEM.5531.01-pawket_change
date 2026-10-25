from datetime import datetime, time, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

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

# The Services page and the AI assistant both read these, so the assistant always quotes the real prices.
SERVICES = [
    {'name': 'Full-Day Daycare', 'price': f'${FULL_DAY_PRICE}', 'unit': '/day', 'included': 'Supervised playtime, rest periods, and general care'},
    {'name': 'Half-Day Daycare', 'price': f'${HALF_DAY_PRICE}', 'unit': '/day', 'included': f'Up to {HALF_DAY_MAX_HOURS} hours of supervised care'},
    {'name': 'Overnight Boarding', 'price': f'${OVERNIGHT_PRICE}', 'unit': '/night', 'included': 'Overnight care, feeding, and daily activities'},
    {'name': 'Basic Grooming', 'price': '$30', 'unit': '', 'included': 'Bath, brushing, and basic cleaning'},
]
ADD_ONS = [
    {'name': 'Extra Walk (20 minutes)', 'price': '$10'},
    {'name': 'Nail Trimming', 'price': '$12'},
    {'name': 'One-on-One Playtime', 'price': '$8'},
]
PRICING_POLICIES = [
    'No membership required to use our services.',
    'No hidden fees or mandatory add-ons.',
    'Every service clearly lists what is included in the price.',
    'You will see your total cost before you book.',
    'Any additional charges are explained before you confirm your booking.',
]


class Booking(models.Model):
    email = models.EmailField()
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
    """Category and priority are filled in by AI after the message is saved; blank means it has not been tagged."""
    CATEGORY_CHOICES = [
        ('booking', 'Booking question'),
        ('pricing', 'Pricing'),
        ('services', 'Services'),
        ('complaint', 'Complaint'),
        ('feedback', 'Feedback'),
        ('other', 'Other'),
    ]
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(max_length=2000)
    submitted_at = models.DateTimeField(auto_now_add=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Message from {self.name} ({self.email})'


class Review(models.Model):
    """Only someone with a booking under this email can leave a review; each email has one review, which it can edit.

    Reviews that AI moderation flags stay pending, and hidden, until staff publish them in the admin.
    """
    PUBLISHED = 'published'
    PENDING = 'pending'
    STATUS_CHOICES = [
        (PUBLISHED, 'Published'),
        (PENDING, 'Pending staff check'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PUBLISHED)
    owner_reply = models.TextField(blank=True, help_text='Shown publicly under the review.')
    owner_reply_draft = models.TextField(blank=True, help_text='AI-drafted reply for staff to edit. Never shown publicly.')

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(Lower('email'), name='one_review_per_email'),
        ]

    def __str__(self):
        return f'{self.rating}-star review from {self.name}'


class ReviewSummary(models.Model):
    """A single AI-written summary of published reviews, regenerated on the next page view after reviews change."""
    text = models.TextField(blank=True)
    review_count = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(null=True, blank=True)
    is_stale = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'review summary'

    def __str__(self):
        return f'Summary of {self.review_count} reviews'


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def mark_review_summary_stale(**kwargs):
    ReviewSummary.objects.update(is_stale=True)
