from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader


def home(request):
    template = loader.get_template('home.html')
    return HttpResponse(template.render({}, request))


def services(request):
    service_list = [
        {'name': 'Full-Day Daycare', 'price': '$25', 'unit': '/day', 'included': 'Supervised playtime, rest periods, and general care'},
        {'name': 'Half-Day Daycare', 'price': '$15', 'unit': '/day', 'included': 'Up to 4 hours of supervised care'},
        {'name': 'Overnight Boarding', 'price': '$45', 'unit': '/night', 'included': 'Overnight care, feeding, and daily activities'},
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
