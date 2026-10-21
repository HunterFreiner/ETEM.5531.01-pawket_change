from django.contrib import admin

from .models import Booking, ContactMessage


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['check_in_date', 'drop_off_time', 'check_out_date', 'pickup_time', 'created_at']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    readonly_fields = ['name', 'email', 'message', 'submitted_at']
