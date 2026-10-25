from django.contrib import admin, messages

from . import ai
from .models import Booking, ContactMessage, Pet, Review, ReviewSummary


class PetInline(admin.StackedInline):
    model = Pet
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['owner_name', 'email', 'phone', 'number_of_pets', 'check_in_date', 'grooming_date', 'created_at']
    search_fields = ['owner_name', 'email', 'phone', 'pets__name']
    inlines = [PetInline]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    # Category and priority are tagged by AI but stay editable so staff can correct them.
    list_display = ['name', 'email', 'category', 'priority', 'submitted_at']
    list_filter = ['priority', 'category']
    search_fields = ['name', 'email', 'message']
    readonly_fields = ['name', 'email', 'message', 'submitted_at']
    actions = ['retag_with_ai']

    @admin.action(description='Re-run AI tagging on selected messages')
    def retag_with_ai(self, request, queryset):
        tagged = sum(1 for message in queryset if ai.tag_contact_message(message))
        level = messages.SUCCESS if tagged == len(queryset) else messages.WARNING
        self.message_user(request, f'Tagged {tagged} of {len(queryset)} messages.', level)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'rating', 'status', 'created_at']
    list_filter = ['status', 'rating']
    search_fields = ['name', 'email', 'comment']
    actions = ['publish', 'hide', 'draft_reply_with_ai']

    @admin.action(description='Publish selected reviews')
    def publish(self, request, queryset):
        for review in queryset:
            review.status = Review.PUBLISHED
            review.save(update_fields=['status'])
        self.message_user(request, f'Published {len(queryset)} reviews.', messages.SUCCESS)

    @admin.action(description='Hide selected reviews (set to pending)')
    def hide(self, request, queryset):
        for review in queryset:
            review.status = Review.PENDING
            review.save(update_fields=['status'])
        self.message_user(request, f'Hid {len(queryset)} reviews.', messages.SUCCESS)

    @admin.action(description='Draft a reply with AI (saved as a draft, not posted)')
    def draft_reply_with_ai(self, request, queryset):
        drafted = 0
        for review in queryset:
            draft = ai.draft_review_reply(review)
            if draft:
                review.owner_reply_draft = draft
                review.save(update_fields=['owner_reply_draft'])
                drafted += 1
        level = messages.SUCCESS if drafted == len(queryset) else messages.WARNING
        self.message_user(
            request,
            f'Drafted {drafted} of {len(queryset)} replies. Open a review to edit its draft and copy it into Owner reply.',
            level,
        )


@admin.register(ReviewSummary)
class ReviewSummaryAdmin(admin.ModelAdmin):
    list_display = ['review_count', 'generated_at', 'is_stale']
    readonly_fields = ['review_count', 'generated_at']
