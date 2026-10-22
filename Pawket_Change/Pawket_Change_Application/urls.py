from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('services', views.services, name='services'),
    path('about', views.about, name='about'),
    path('reviews', views.reviews, name='reviews'),
    path('contact', views.contact, name='contact'),
    path('book', views.book, name='book'),
    path('book/confirmation/<int:booking_id>', views.booking_confirmation, name='booking_confirmation'),
]
