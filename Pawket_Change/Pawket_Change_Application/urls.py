from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('services', views.services, name='services'),
    path('about', views.about, name='about'),
    path('reviews', views.reviews, name='reviews'),
    path('contact', views.contact, name='contact'),
    path('contact/chat', views.contact_chat, name='contact_chat'),
    path('contact/chat/handoff', views.contact_chat_handoff, name='contact_chat_handoff'),
    path('book', views.book, name='book'),
    path('book/chat', views.booking_chat, name='booking_chat'),
    path('book/confirmation/<int:booking_id>', views.booking_confirmation, name='booking_confirmation'),
]
