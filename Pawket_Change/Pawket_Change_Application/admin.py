from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['check_in_date', 'drop_off_time', 'check_out_date', 'pickup_time', 'created_at']
