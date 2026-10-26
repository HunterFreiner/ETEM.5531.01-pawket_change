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

# Each booking covers 1 to MAX_PETS dogs, and every price is per dog.
MAX_PETS = 3

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

# The Services page, the booking form, and the AI assistant all read these lists, so every page quotes the same prices.
SERVICES = [
    {'name': 'Full-Day Daycare', 'price': f'${FULL_DAY_PRICE}', 'unit': '/day', 'included': 'Supervised playtime, rest periods, and general care'},
    {'name': 'Half-Day Daycare', 'price': f'${HALF_DAY_PRICE}', 'unit': '/day', 'included': f'Up to {HALF_DAY_MAX_HOURS} hours of supervised care'},
    {'name': 'Overnight Boarding', 'price': f'${OVERNIGHT_PRICE}', 'unit': '/night', 'included': 'Overnight care, feeding, and daily activities'},
]
ADD_ONS = [
    {'name': 'Extra Walk (20 minutes)', 'price': '$10'},
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
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    STATUS_CHOICES = [(PENDING, 'Awaiting approval'), (CONFIRMED, 'Confirmed')]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    submission_key = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    owner_name = models.CharField(max_length=100, default='')
    email = models.EmailField()
    phone = models.CharField(max_length=20, default='')
    number_of_pets = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(MAX_PETS)],
    )
    notes = models.TextField(max_length=1000, blank=True)

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
    def reference(self):
        return f'PC-{self.pk:06d}'

    @property
    def stay_service_name(self):
        if not self.includes_stay:
            return ''
        if self.nights:
            return 'Overnight Boarding'
        return 'Half-Day Daycare' if self.stay_cost_per_pet == HALF_DAY_PRICE else 'Full-Day Daycare'

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
    def stay_cost_per_pet(self):
        """Overnight stays are charged per night; same-day stays are half-day or full-day daycare."""
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
    def cost(self):
        return self.stay_cost_per_pet * self.number_of_pets

    @property
    def grooming_cost_per_pet(self):
        return sum(
            GROOMING_PRICES.get(service, 0)
            for service in self.grooming_services
        )

    @property
    def grooming_cost(self):
        return self.grooming_cost_per_pet * self.number_of_pets

    @property
    def total_cost(self):
        return self.cost + self.grooming_cost


class BookingNotification(models.Model):
    """Durable outbox. Delivery status is independent of booking approval."""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='notifications')
    booking_status = models.CharField(max_length=12, choices=Booking.STATUS_CHOICES)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    state = models.CharField(max_length=12, default='pending', choices=[
        ('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Accepted by mail server'),
        ('failed', 'Failed'), ('preview', 'Development preview'),
    ])
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class Pet(models.Model):
    """A dog on a booking, with the details and care needs staff should know about."""
    SIZE_CHOICES = [
        ('small', 'Small (under 20 lb)'),
        ('medium', 'Medium (20–50 lb)'),
        ('large', 'Large (50–90 lb)'),
        ('extra_large', 'Extra large (over 90 lb)'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='pets')
    name = models.CharField(max_length=50)
    breed = models.CharField(max_length=60)
    size = models.CharField(max_length=20, choices=SIZE_CHOICES)
    age = models.PositiveSmallIntegerField(validators=[MaxValueValidator(30)], help_text='In years. Enter 0 for puppies under 1.')
    special_instructions = models.TextField(max_length=1000, blank=True)
    medications = models.TextField(max_length=1000, blank=True)
    dietary_needs = models.TextField(max_length=1000, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ({self.breed})'



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
