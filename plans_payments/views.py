import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import View
from payments import PaymentStatus, RedirectNeeded, get_payment_model
from plans.models import Order

# An attempt while another one is in flight (or just captured) joins it
# instead of creating a twin payment.
IN_FLIGHT_STATUSES = (
    PaymentStatus.WAITING,
    PaymentStatus.INPUT,
    PaymentStatus.PREAUTH,
    PaymentStatus.CONFIRMED,
)
DECLINED_STATUSES = (PaymentStatus.REJECTED, PaymentStatus.ERROR)


class PaymentDetailView(LoginRequiredMixin, View):
    login_url = reverse_lazy("auth_login")
    template_name = "plans_payments/payment.html"

    def get(self, request, *args, payment_id=None):
        payment = get_object_or_404(get_payment_model(), order__user=request.user, id=payment_id)
        try:
            form = payment.get_form(data=request.POST or None)
        except RedirectNeeded as redirect_to:
            payment.save()
            return redirect(str(redirect_to))
        return TemplateResponse(request, "plans_payments/payment.html", {"form": form, "payment": payment})


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


def create_payment_object(payment_variant, order, request=None, autorenewed_payment=False):
    Payment = get_payment_model()
    if hasattr(order.user.userplan, "recurring") and order.user.userplan.recurring.payment_provider != payment_variant:
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
    """Create a charge attempt for an order -- idempotently.

    Every GET used to create a fresh ``Payment``; users re-clicking through
    a slow redirect or a decline produced bursts of live charge attempts
    (duplicate captures at worst, bank anti-fraud blocks at best). Two
    guards make the endpoint idempotent instead:

    * an attempt while a previous one is in flight (or just succeeded)
      joins it -- the user is redirected to the existing payment
      (``PLANS_PAYMENTS_JOIN_IN_FLIGHT_SECONDS``, default 180; 0 disables);
    * an attempt right after a decline waits out a cooldown, because banks
      read rapid-fire retries as fraud
      (``PLANS_PAYMENTS_DECLINE_COOLDOWN_SECONDS``, default 60; 0 disables).

    Both windows look across all the user's orders: retry bursts typically
    mint a new order per click.
    """

    login_url = reverse_lazy("auth_login")

    def get(self, request, *args, order_id=None, payment_variant=None):
        order = get_object_or_404(Order, pk=order_id, user=request.user)
        Payment = get_payment_model()
        now = timezone.now()

        join_window = getattr(settings, "PLANS_PAYMENTS_JOIN_IN_FLIGHT_SECONDS", 180)
        if join_window:
            in_flight = (
                Payment.objects.filter(
                    order__user=request.user,
                    status__in=IN_FLIGHT_STATUSES,
                    created__gte=now - datetime.timedelta(seconds=join_window),
                )
                .order_by("-created")
                .first()
            )
            if in_flight is not None:
                messages.info(
                    request,
                    _("Your previous payment attempt is still being processed - continuing with it."),
                )
                return redirect(reverse("payment_details", kwargs={"payment_id": in_flight.id}))

        decline_cooldown = getattr(settings, "PLANS_PAYMENTS_DECLINE_COOLDOWN_SECONDS", 60)
        if decline_cooldown:
            recently_declined = Payment.objects.filter(
                order__user=request.user,
                status__in=DECLINED_STATUSES,
                created__gte=now - datetime.timedelta(seconds=decline_cooldown),
            ).exists()
            if recently_declined:
                messages.warning(
                    request,
                    _(
                        "Your previous charge attempt was declined a moment ago. "
                        "Please wait a minute before trying again - rapid retries "
                        "can make your bank block the card."
                    ),
                )
                return redirect(reverse("order", kwargs={"pk": order.pk}))

        payment = create_payment_object(payment_variant, order, request)
        return redirect(reverse("payment_details", kwargs={"payment_id": payment.id}))
