from django.contrib import admin

from .models import Booking, ContactMessage, Review


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['email', 'check_in_date', 'drop_off_time', 'check_out_date', 'pickup_time', 'created_at']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    readonly_fields = ['name', 'email', 'message', 'submitted_at']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'rating', 'created_at']
    search_fields = ['name', 'email', 'comment']
