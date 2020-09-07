from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from payments import get_payment_model, RedirectNeeded
from plans.models import Order


def payment_details(request, payment_id):
    payment = get_object_or_404(get_payment_model(), id=payment_id)
    try:
        form = payment.get_form(data=request.POST or None)
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))
    return TemplateResponse(request, 'plans_payments/payment.html',
                            {'form': form, 'payment': payment})


def get_client_ip(request):
    return request.META.get('REMOTE_ADDR')


def create_payment_object(payment_variant, order, request=None):
    Payment = get_payment_model()
    if hasattr(order.user.userplan, 'recurring') and order.user.userplan.recurring.payment_provider != payment_variant:
        order.user.userplan.recurring.delete()
    return Payment.objects.create(
        variant=payment_variant,
        order=order,
        description='Subscription plan %s purchase' % order.name,
        total=Decimal(order.total()),
        tax=Decimal(order.tax_total()),
        currency=order.currency,
        delivery=Decimal(0),
        billing_first_name=settings.PLANS_INVOICE_ISSUER['issuer_name'],
        # billing_last_name=settings.PLANS_INVOICE_ISSUER['issuer_'],
        billing_address_1=settings.PLANS_INVOICE_ISSUER['issuer_street'],
        # billing_address_2=settings.PLANS_INVOICE_ISSUER['issuer_'],
        billing_city=settings.PLANS_INVOICE_ISSUER['issuer_city'],
        billing_postcode=settings.PLANS_INVOICE_ISSUER['issuer_zipcode'],
        billing_country_code=settings.PLANS_INVOICE_ISSUER['issuer_country'],
        # billing_country_area=settings.PLANS_INVOICE_ISSUER['issuer_name'],
        customer_ip_address=get_client_ip(request) if request else '127.0.0.1',
    )


def create_payment(request, payment_variant, order_id):
    order = get_object_or_404(Order, pk=order_id)
    payment = create_payment_object(payment_variant, order, request)
    return redirect(reverse('payment_details', kwargs={'payment_id': payment.id}))
