import json
import logging
from decimal import Decimal

from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse

from payments import PurchasedItem
from payments.core import provider_factory
from payments.models import BasePayment
from payments.signals import status_changed
from payments.payu_api import CVV2Required

from plans.models import Order
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
        return self.order.user.userplan.recurring_token

    def store_renew_token(self, token):
        """
        Store the recurring payments renew token for user of this payment
        The renew token is string defined by the provider
        Used by PayU provider for now
        """
        self.order.user.userplan.automatic_renewal = True
        self.order.user.userplan.recurring_pricing = self.order.pricing
        self.order.user.userplan.recurring_token = token
        self.order.user.userplan.recurring_amount = self.order.amount
        self.order.user.userplan.recurring_tax = self.order.tax
        self.order.user.userplan.recurring_currency = self.order.currency
        self.order.user.userplan.save()

    def auto_complete_recurring(self):
        provider = provider_factory(self.variant)
        provider.auto_complete_recurring(self)


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
        pricing=userplan.recurring_pricing,
        amount=userplan.recurring_amount,
        tax=userplan.recurring_tax,
        currency=userplan.recurring_currency,
    )
    payment = create_payment_object('payu-recurring', order)
    try:
        payment.auto_complete_recurring()
    except CVV2Required as e:
        print("CVV2 code is required, enter it at %s" % e.get_form_url())
    order = payment.order
    if payment.status == 'confirmed':
        order.complete_order()
