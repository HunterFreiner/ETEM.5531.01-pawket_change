import json
import logging
import time as clock
from datetime import date, datetime

from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ai
from .forms import BookingForm, ContactForm, ReviewEmailForm, ReviewForm, booked_slots
from .models import (
    ADD_ONS, BUSINESS_HOURS, FULL_DAY_PRICE, GROOMING_PRICES, HALF_DAY_MAX_HOURS, HALF_DAY_PRICE, OVERNIGHT_PRICE,
    PRICING_POLICIES, SERVICES, Booking, ContactMessage, Review,
)

# Limits for the Contact page chat, so one visitor can't run up the API bill.
CHAT_MAX_TURNS = 20
CHAT_MAX_MESSAGE_LENGTH = 1000
CHAT_MESSAGES_PER_HOUR = 20
CHAT_UNAVAILABLE_REPLY = (
    "Sorry, I can't answer right now. You can send your question to our team on the Contact Us page."
)


logger = logging.getLogger(__name__)


def home(request):
    template = loader.get_template('home.html')
    return HttpResponse(template.render({}, request))


def services(request):
    template = loader.get_template('services.html')

    context = {
        'services': SERVICES,
        'add_ons': ADD_ONS,
        'policies': PRICING_POLICIES,
    }

    return HttpResponse(template.render(context, request))


def about(request):
    template = loader.get_template('about.html')
    return HttpResponse(template.render({}, request))


def contact(request):
    form = ContactForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            contact_message = form.save()
        except DatabaseError:
            logger.exception('Unable to save a contact message.')
            form.add_error(
                None,
                'We could not send your message right now. Please try again later.',
            )
        else:
            ai.tag_contact_message(contact_message)
            messages.success(
                request,
                'Thanks for reaching out. We received your message and will get back to you as soon as we can.',
            )
            return redirect('contact')

    context = {
        'form': form,
        'business_hours': BUSINESS_HOURS,
        'contact_phone': settings.CONTACT_PHONE or '314-555-0142',
        'contact_email': settings.CONTACT_EMAIL or 'hello@pawketchange.org',
        'contact_address': settings.CONTACT_ADDRESS or '100 Treat Street, St. Louis, MO 63101',
        'ai_enabled': ai.is_enabled(),
    }

    return render(request, 'contact.html', context)


def _clean_chat_history(raw_messages):
    """Keep only well-formed text turns that alternate user/assistant and end with the user, or return None."""
    if not isinstance(raw_messages, list) or not raw_messages:
        return None
    history = []
    for item in raw_messages[-CHAT_MAX_TURNS:]:
        if not isinstance(item, dict):
            return None
        role, content = item.get('role'), item.get('content')
        if role not in ('user', 'assistant') or not isinstance(content, str) or not content.strip():
            return None
        history.append({'role': role, 'content': content.strip()[:CHAT_MAX_MESSAGE_LENGTH]})
    while history and history[0]['role'] != 'user':
        history.pop(0)
    if not history or history[-1]['role'] != 'user':
        return None
    if any(a['role'] == b['role'] for a, b in zip(history, history[1:])):
        return None
    return history


def _chat_rate_limited(request):
    hour_ago = clock.time() - 3600
    recent = [t for t in request.session.get('chat_times', []) if t > hour_ago]
    if len(recent) >= CHAT_MESSAGES_PER_HOUR:
        return True
    request.session['chat_times'] = recent + [clock.time()]
    return False


def _read_json(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _chat(request, page):
    data = _read_json(request)
    history = _clean_chat_history(data.get('messages') if isinstance(data, dict) else None)
    if history is None:
        return JsonResponse({'error': 'Invalid chat message.'}, status=400)
    if _chat_rate_limited(request):
        return JsonResponse({
            'reply': "You've sent a lot of messages in the last hour. Please send your question to our team on the Contact Us page.",
            'booking': None,
            'recommendations': None,
        }, status=429)
    result = ai.chat_reply(history, page=page)
    if result is None:
        return JsonResponse({'reply': CHAT_UNAVAILABLE_REPLY, 'booking': None, 'recommendations': None})
    return JsonResponse(result)


@require_POST
def contact_chat(request):
    return _chat(request, 'contact')


@require_POST
def booking_chat(request):
    return _chat(request, 'booking')


def _chat_transcript(history):
    """The chat as a contact message, trimmed from the start so the latest turns fit in the message field."""
    header = 'Sent from the website chat assistant.\n\n'
    limit = ContactMessage._meta.get_field('message').max_length - len(header)
    lines = [f'{"Customer" if turn["role"] == "user" else "Assistant"}: {turn["content"]}' for turn in history]
    transcript = '\n\n'.join(lines)
    if len(transcript) > limit:
        transcript = '...' + transcript[-(limit - 3):]
    return header + transcript


@require_POST
def contact_chat_handoff(request):
    data = _read_json(request)
    if not isinstance(data, dict):
        return JsonResponse({'error': 'Invalid request.'}, status=400)
    raw_messages = data.get('messages')
    history = []
    if isinstance(raw_messages, list):
        history = [
            {'role': m['role'], 'content': m['content'].strip()[:CHAT_MAX_MESSAGE_LENGTH]}
            for m in raw_messages[-CHAT_MAX_TURNS:]
            if isinstance(m, dict) and m.get('role') in ('user', 'assistant')
            and isinstance(m.get('content'), str) and m['content'].strip()
        ]
    if not any(turn['role'] == 'user' for turn in history):
        return JsonResponse({'errors': {'messages': ['Ask a question in the chat first.']}}, status=400)

    form = ContactForm({
        'name': data.get('name', ''),
        'email': data.get('email', ''),
        'message': _chat_transcript(history),
    })
    if not form.is_valid():
        errors = {field: [str(error) for error in field_errors] for field, field_errors in form.errors.items()}
        return JsonResponse({'errors': errors}, status=400)
    try:
        contact_message = form.save()
    except DatabaseError:
        logger.exception('Unable to save a chat handoff.')
        return JsonResponse({'errors': {'__all__': ['We could not send this right now. Please try again later.']}}, status=500)
    ai.tag_contact_message(contact_message)
    return JsonResponse({'ok': True})


def reviews(request):
    # A guest first proves they have a booking by entering its email.
    # That email is kept in the session so the review form can only
    # be submitted for a recognized booking.
    # If that email already has a review, the form edits it instead
    # of creating a second one.

    verified_email = request.session.get('review_email')

    existing_review = (
        Review.objects.filter(email__iexact=verified_email).first()
        if verified_email
        else None
    )

    email_form = ReviewEmailForm()

    review_form = (
        ReviewForm(instance=existing_review)
        if verified_email
        else None
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'verify':
            email_form = ReviewEmailForm(request.POST)

            if email_form.is_valid():
                request.session['review_email'] = email_form.cleaned_data['email']
                return redirect('reviews')

        elif action == 'change_email':
            request.session.pop('review_email', None)
            return redirect('reviews')

        elif action == 'delete' and existing_review:
            existing_review.delete()
            request.session.pop('review_email', None)
            messages.success(request, 'Your review has been deleted.')
            return redirect('reviews')

        elif action == 'submit' and verified_email:
            review_form = ReviewForm(
                request.POST,
                instance=existing_review,
            )

            if review_form.is_valid():
                review = review_form.save(commit=False)

                if existing_review:
                    review.edited_at = timezone.now()
                    success = 'Your review has been updated.'
                else:
                    review.email = verified_email
                    success = 'Thanks for your review! It is now posted below.'
                # If AI moderation is unavailable, the review is published as usual.
                check = ai.moderate_review(review.name, review.rating, review.comment)
                if check and not check.publish:
                    review.status = Review.PENDING
                    success = 'Thanks for your review! It will appear here after a quick check by our team.'
                else:
                    review.status = Review.PUBLISHED
                review.save()
                request.session.pop('review_email', None)
                messages.success(request, success)

                return redirect('reviews')

    review_list = Review.objects.filter(status=Review.PUBLISHED)
    context = {
        'reviews': review_list,
        'review_summary': ai.review_summary(),
        'average_rating': review_list.aggregate(Avg('rating'))['rating__avg'],
        'email_form': email_form,
        'review_form': review_form,
        'verified_email': verified_email,
        'existing_review': existing_review,
    }

    return render(request, 'reviews.html', context)


def book(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        action = request.POST.get('action')

        if form.is_valid() and action != 'edit':
            if action == 'confirm':
                booking = form.save()

                return redirect(
                    'booking_confirmation',
                    booking_id=booking.id,
                )

            return render(
                request,
                'booking_review.html',
                {
                    'form': form,
                    'booking': form.instance,
                },
            )
    else:
        form = BookingForm(initial=_booking_prefill(request.GET))
    now = timezone.localtime()

    availability = {
        'booked': booked_slots(),
        'today': now.date().isoformat(),
        'now': now.strftime('%H:%M'),
    }

    # Pricing information for the live booking estimate
    context = {
        'form': form,
        'business_hours': BUSINESS_HOURS,
        'availability': availability,
        'ai_enabled': ai.is_enabled(),
        'pricing': {
            'full_day': FULL_DAY_PRICE,
            'half_day': HALF_DAY_PRICE,
            'half_day_max_hours': HALF_DAY_MAX_HOURS,
            'overnight': OVERNIGHT_PRICE,
            'grooming': GROOMING_PRICES,
        },
    }

    return render(request, 'booking.html', context)


def _booking_prefill(params):
    """Booking details from a chat assistant link. Badly formatted values are dropped; the form checks the rest on submit."""
    prefill = {}
    for field in ('check_in_date', 'check_out_date'):
        try:
            prefill[field] = date.fromisoformat(params.get(field, ''))
        except ValueError:
            pass
    for field in ('drop_off_time', 'pickup_time'):
        try:
            prefill[field] = datetime.strptime(params.get(field, ''), '%H:%M').strftime('%H:%M')
        except ValueError:
            pass
    return prefill


def booking_confirmation(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    return render(
        request,
        'booking_confirmation.html',
        {
            'booking': booking,
        },
    )
