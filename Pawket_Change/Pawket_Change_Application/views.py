import logging

from django.conf import settings
from django.contrib import messages
from django.db import DatabaseError
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.template import loader
from django.utils import timezone

from .forms import BookingForm, ContactForm, ReviewEmailForm, ReviewForm, booked_slots
from .models import Booking, Review, BUSINESS_HOURS, FULL_DAY_PRICE, HALF_DAY_MAX_HOURS, HALF_DAY_PRICE, OVERNIGHT_PRICE


logger = logging.getLogger(__name__)


def home(request):
    template = loader.get_template('home.html')
    return HttpResponse(template.render({}, request))


def services(request):
    service_list = [
        {'name': 'Full-Day Daycare', 'price': f'${FULL_DAY_PRICE}', 'unit': '/day', 'included': 'Supervised playtime, rest periods, and general care'},
        {'name': 'Half-Day Daycare', 'price': f'${HALF_DAY_PRICE}', 'unit': '/day', 'included': f'Up to {HALF_DAY_MAX_HOURS} hours of supervised care'},
        {'name': 'Overnight Boarding', 'price': f'${OVERNIGHT_PRICE}', 'unit': '/night', 'included': 'Overnight care, feeding, and daily activities'},
        {'name': 'Basic Grooming', 'price': '$30', 'unit': '', 'included': 'Bath, brushing, and basic cleaning'},
    ]
    add_ons = [
        {'name': 'Extra Walk (20 minutes)', 'price': '$10'},
        {'name': 'Nail Trimming', 'price': '$12'},
        {'name': 'One-on-One Playtime', 'price': '$8'},
    ]
    policies = [
        'No membership required to use our services.',
        'No hidden fees or mandatory add-ons.',
        'Every service clearly lists what is included in the price.',
        'You will see your total cost before you book.',
        'Any additional charges are explained before you confirm your booking.',
    ]
    template = loader.get_template('services.html')
    context = {
        'services': service_list,
        'add_ons': add_ons,
        'policies': policies,
    }
    return HttpResponse(template.render(context, request))


def about(request):
    template = loader.get_template('about.html')
    return HttpResponse(template.render({}, request))


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except DatabaseError:
            logger.exception('Unable to save a contact message.')
            form.add_error(None, 'We could not send your message right now. Please try again later.')
        else:
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
    }
    return render(request, 'contact.html', context)


def reviews(request):
    # A guest first proves they have a booking by entering its email; that email is kept in the
    # session so the review form can only be submitted for a recognized booking. If that email already
    # has a review, the form edits it instead of creating a second one.
    verified_email = request.session.get('review_email')
    existing_review = Review.objects.filter(email__iexact=verified_email).first() if verified_email else None
    email_form = ReviewEmailForm()
    review_form = ReviewForm(instance=existing_review) if verified_email else None

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
        elif action == 'submit' and verified_email:
            review_form = ReviewForm(request.POST, instance=existing_review)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                if existing_review:
                    review.edited_at = timezone.now()
                    success = 'Your review has been updated.'
                else:
                    review.email = verified_email
                    success = 'Thanks for your review! It is now posted below.'
                review.save()
                request.session.pop('review_email', None)
                messages.success(request, success)
                return redirect('reviews')

    review_list = Review.objects.all()
    context = {
        'reviews': review_list,
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
                return redirect('booking_confirmation', booking_id=booking.id)
            return render(request, 'booking_review.html', {'form': form, 'booking': form.instance})
    else:
        form = BookingForm()
    now = timezone.localtime()
    availability = {
        'booked': booked_slots(),
        'today': now.date().isoformat(),
        'now': now.strftime('%H:%M'),
    }
    context = {'form': form, 'business_hours': BUSINESS_HOURS, 'availability': availability}
    return render(request, 'booking.html', context)


def booking_confirmation(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'booking_confirmation.html', {'booking': booking})
