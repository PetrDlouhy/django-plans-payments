from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import View
from payments import RedirectNeeded, get_payment_model
from plans.models import Order


class PaymentDetailView(LoginRequiredMixin, View):
    login_url = reverse_lazy("auth_login")
    template_name = "plans_payments/payment.html"

    def get(self, request, *args, payment_id=None):
        payment = get_object_or_404(
            get_payment_model(), order__user=request.user, id=payment_id
        )
        try:
            form = payment.get_form(data=request.POST or None)
        except RedirectNeeded as redirect_to:
            payment.save()
            return redirect(str(redirect_to))
        return TemplateResponse(
            request, "plans_payments/payment.html", {"form": form, "payment": payment}
        )


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


def create_payment_object(
    payment_variant, order, request=None, autorenewed_payment=False
):
    Payment = get_payment_model()
    if (
        hasattr(order.user.userplan, "recurring")
        and order.user.userplan.recurring.payment_provider != payment_variant
    ):
        order.user.userplan.recurring.delete()
    return Payment.objects.create(
        variant=payment_variant,
        order=order,
        description=f"{order.name} purchase",
        total=Decimal(order.total()),
        tax=Decimal(order.tax_total()),
        currency=order.currency,
        delivery=Decimal(0),
        billing_first_name=order.user.first_name,
        billing_last_name=order.user.last_name,
        billing_email=order.user.email or "",
        billing_address_1=order.user.billinginfo.street,
        # billing_address_2=order.user.billinginfo.zipcode,
        billing_city=order.user.billinginfo.city,
        billing_postcode=order.user.billinginfo.zipcode,
        billing_country_code=order.user.billinginfo.country,
        # billing_country_area=order.user.billinginfo.zipcode,
        customer_ip_address=get_client_ip(request) if request else "127.0.0.1",
        autorenewed_payment=autorenewed_payment,
    )


class CreatePaymentView(LoginRequiredMixin, View):
    login_url = reverse_lazy("auth_login")

    def get(self, request, *args, order_id=None, payment_variant=None):
        order = get_object_or_404(Order, pk=order_id, user=request.user)
        payment = create_payment_object(payment_variant, order, request)
        return redirect(reverse("payment_details", kwargs={"payment_id": payment.id}))
