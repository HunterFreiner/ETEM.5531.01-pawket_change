"""Booking emails are queued in the transaction and sent only after commit."""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone

from .models import BookingNotification

logger = logging.getLogger(__name__)


def queue_booking_notification(booking):
    notice = BookingNotification.objects.create(
        booking=booking, recipient=booking.email,
        subject=f'Pawket Change booking confirmed - {booking.reference}',
        body=render_to_string('emails/booking_notification.txt', {
            'booking': booking, 'contact_email': settings.CONTACT_EMAIL,
            'contact_phone': settings.CONTACT_PHONE, 'business_timezone': settings.TIME_ZONE,
        }),
    )
    transaction.on_commit(lambda: deliver_booking_notification(notice.pk), robust=True)
    return notice


def deliver_booking_notification(notice_id):
    # Atomic claim prevents two normal workers from sending the same queued item.
    claimed = BookingNotification.objects.filter(pk=notice_id, state__in=['pending', 'failed']).update(
        state='sending', attempts=F('attempts') + 1, last_error='',
    )
    if not claimed:
        return False
    notice = BookingNotification.objects.get(pk=notice_id)
    try:
        if not settings.DEFAULT_FROM_EMAIL:
            raise ValueError('A verified sender address must be configured')
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.dummy.EmailBackend':
            raise ValueError('Dummy email backend cannot deliver notifications')
        message = EmailMessage(
            notice.subject, notice.body, settings.DEFAULT_FROM_EMAIL, [notice.recipient],
            reply_to=[settings.CONTACT_EMAIL] if settings.CONTACT_EMAIL else [],
        )
        if message.send(fail_silently=False) != 1:
            raise RuntimeError('Mail backend did not accept the message')
        preview = settings.EMAIL_BACKEND in {
            'django.core.mail.backends.console.EmailBackend',
            'django.core.mail.backends.filebased.EmailBackend',
            'django.core.mail.backends.locmem.EmailBackend',
        }
        BookingNotification.objects.filter(pk=notice_id).update(
            state='preview' if preview else 'sent', sent_at=None if preview else timezone.now(),
        )
        return True
    except Exception as exc:
        # Do not log addresses, message bodies, SMTP credentials or provider error text.
        BookingNotification.objects.filter(pk=notice_id).update(state='failed', last_error=type(exc).__name__)
        logger.warning('Booking notification %s failed (%s)', notice_id, type(exc).__name__)
        return False
