
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Pawket_Change_Application', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Testimonial',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID'
                    )
                ),
                (
                    'customer_name',
                    models.CharField(max_length=100)
                ),
                (
                    'pet_name',
                    models.CharField(max_length=100, blank=True)
                ),
                (
                    'review_text',
                    models.TextField()
                ),
                (
                    'rating',
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        choices=[
                            (1, '1 Star'),
                            (2, '2 Stars'),
                            (3, '3 Stars'),
                            (4, '4 Stars'),
                            (5, '5 Stars')
                        ]
                    )
                ),
                (
                    'is_approved',
                    models.BooleanField(default=False)
                ),
                (
                    'is_verified',
                    models.BooleanField(default=False)
                ),
                (
                    'created_at',
                    models.DateTimeField(auto_now_add=True)
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

