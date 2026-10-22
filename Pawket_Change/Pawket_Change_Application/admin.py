#from django.contrib import admin

#from .models import Booking


#@admin.register(Booking)
#class BookingAdmin(admin.ModelAdmin):
#    list_display = ['check_in_date', 'drop_off_time', 'check_out_date', 'pickup_time', 'created_at']




from django.contrib import admin

from .models import Booking, Testimonial


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'check_in_date',
        'drop_off_time',
        'check_out_date',
        'pickup_time',
        'created_at'
    ]


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name',
        'pet_name',
        'rating',
        'is_verified',
        'is_approved',
        'created_at'
    ]

    list_filter = [
        'is_verified',
        'is_approved',
        'rating'
    ]

    search_fields = [
        'customer_name',
        'pet_name',
        'review_text'
    ]

    list_editable = [
        'is_verified',
        'is_approved'
    ]

    readonly_fields = ['created_at']
