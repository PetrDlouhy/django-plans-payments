import json
import logging
from decimal import Decimal

from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail

from payments import PurchasedItem, PaymentStatus
from payments.models import BasePayment
from payments.signals import status_changed

from plans.models import Order, RecurringUserPlan
from plans.signals import account_automatic_renewal

from .views import create_payment_object

logger = logging.getLogger(__name__)


class Payment(BasePayment):
    order = models.ForeignKey(
        'plans.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    transaction_fee = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal('0.0'),
    )

    def save(self, **kwargs):
        if hasattr(self, 'extra_data') and self.extra_data:
            extra_data = json.loads(self.extra_data)
            if 'response' in extra_data:
                transactions = extra_data['response']['transactions']
                for transaction in transactions:
                    related_resources = transaction['related_resources']
                    if len(related_resources) == 1:
                        sale = related_resources[0]['sale']
                        if 'transaction_fee' in sale:
                            self.transaction_fee += Decimal(sale['transaction_fee']['value'])
                        else:
                            logger.warning(
                                'Payment fee not included',
                                extra={
                                    'extra_data': extra_data,
                                },
                            )
        ret_val = super().save(**kwargs)
        return ret_val

    def get_failure_url(self):
        return reverse('order_payment_failure', kwargs={'pk': self.order.pk})

    def get_success_url(self):
        return reverse('order_payment_success', kwargs={'pk': self.order.pk})

    def get_payment_url(self):
        return reverse('payment_details', kwargs={'payment_id': self.pk})

    def get_purchased_items(self):
        yield PurchasedItem(
            name=self.description,
            sku=self.order.pk,
            quantity=1,
            price=self.order.amount,
            currency=self.currency,
        )

    def get_renew_token(self):
        """
        Get the recurring payments renew token for user of this payment
        Used by PayU provider for now
        """
        try:
            return self.order.user.userplan.recurring.token
        except ObjectDoesNotExist:
            return None

    def set_renew_token(self, token, card_expire_year=None, card_expire_month=None):
        """
        Store the recurring payments renew token for user of this payment
        The renew token is string defined by the provider
        Used by PayU provider for now
        """
        recurring, _ = RecurringUserPlan.objects.get_or_create(userplan=self.order.user.userplan)
        recurring.automatic_renewal = True
        recurring.pricing = self.order.pricing
        recurring.token = token
        recurring.amount = self.order.amount
        recurring.tax = self.order.tax
        recurring.currency = self.order.currency
        recurring.card_expire_year = card_expire_year
        recurring.card_expire_month = card_expire_month
        recurring.save()


@receiver(status_changed)
def change_payment_status(sender, *args, **kwargs):
    payment = kwargs['instance']
    order = payment.order
    if payment.status == 'confirmed':
        order.complete_order()


@receiver(account_automatic_renewal)
def renew_accounts(sender, user, *args, **kwargs):
    userplan = user.userplan
    order = Order.objects.create(
        user=user,
        plan=userplan.plan,
        pricing=userplan.recurring.pricing,
        amount=userplan.recurring.amount,
        tax=userplan.recurring.tax,
        currency=userplan.recurring.currency,
    )
    # TODO: don't hardwire the payment provider name
    payment = create_payment_object('payu-recurring', order)
    redirect_url = payment.auto_complete_recurring()
    if redirect_url != 'success':
        print("CVV2/3DS code is required, enter it at %s" % redirect_url)
        send_mail(
            'Recurring payment - action required',
            'Please renew your CVV2/3DS at %s' % redirect_url,
            'noreply@blenderkit.com',
            [payment.order.user.email],
            fail_silently=False,
        )
    order = payment.order
    if payment.status == 'confirmed':
        order.complete_order()
