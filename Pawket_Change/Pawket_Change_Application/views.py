from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.template import loader
from django.utils import timezone

from .forms import BookingForm, booked_slots
from .models import Booking, BUSINESS_HOURS, FULL_DAY_PRICE, HALF_DAY_MAX_HOURS, HALF_DAY_PRICE, OVERNIGHT_PRICE


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
    template = loader.get_template('contact.html')
    return HttpResponse(template.render({}, request))


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
