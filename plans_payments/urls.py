from django.urls import path

from .views import CreatePaymentView, PaymentDetailView

urlpatterns = [
    path(
        "payment_details/<int:payment_id>/",
        PaymentDetailView.as_view(),
        name="payment_details",
    ),
    path(
        "create_payment/<str:payment_variant>/<int:order_id>/",
        CreatePaymentView.as_view(),
        name="create_payment",
    ),
]
