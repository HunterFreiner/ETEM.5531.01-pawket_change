from django.core.management.base import BaseCommand

from ...models import BookingNotification
from ...notifications import deliver_booking_notification


class Command(BaseCommand):
    help = 'Retry pending or failed booking emails. Never re-sends sent or preview items.'

    def handle(self, *args, **options):
        sent = 0
        for pk in BookingNotification.objects.filter(state__in=['pending', 'failed']).values_list('pk', flat=True):
            notice = BookingNotification.objects.select_related('booking').get(pk=pk)
            # Do not send stale pending-approval copy after staff have approved a booking.
            if notice.booking_status != notice.booking.status:
                continue
            sent += bool(deliver_booking_notification(pk))
        self.stdout.write(f'Processed successfully: {sent}')
