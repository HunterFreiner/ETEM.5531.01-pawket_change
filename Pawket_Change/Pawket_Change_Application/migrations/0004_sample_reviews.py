from django.db import migrations

# Sample reviews so the Reviews page has content for demos. Delete them in the admin before launch.
SAMPLE_REVIEWS = [
    ('Maya R.', 'maya.sample@example.com', 5, 'Biscuit came home tired and happy after a full day of daycare. The staff sent us a quick update at lunch, which was a nice touch.'),
    ('Jordan P.', 'jordan.sample@example.com', 5, 'Clear pricing and no surprise fees. Booking an overnight stay took two minutes and our pup was well cared for.'),
    ('Alex T.', 'alex.sample@example.com', 4, 'Great half-day option for our anxious rescue. Drop-off was smooth and the team remembered his routine.'),
    ('Sam L.', 'sam.sample@example.com', 5, 'The basic grooming was a great value. Our dog looked and smelled fantastic.'),
]


def add_sample_reviews(apps, schema_editor):
    Review = apps.get_model('Pawket_Change_Application', 'Review')
    for name, email, rating, comment in SAMPLE_REVIEWS:
        Review.objects.create(name=name, email=email, rating=rating, comment=comment)


def remove_sample_reviews(apps, schema_editor):
    Review = apps.get_model('Pawket_Change_Application', 'Review')
    Review.objects.filter(email__in=[email for _, email, _, _ in SAMPLE_REVIEWS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('Pawket_Change_Application', '0003_booking_email_review'),
    ]

    operations = [
        migrations.RunPython(add_sample_reviews, remove_sample_reviews),
    ]
