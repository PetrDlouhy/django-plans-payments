from django.urls import path

from .views import create_payment, payment_details


urlpatterns = [
    path('payment_details/<int:payment_id>/', payment_details, name='payment_details'),
    path('create_payment/<str:payment_variant>/<int:order_id>/', create_payment, name='create_payment'),
]
