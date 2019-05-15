import json
import logging
from decimal import Decimal

from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse

from payments import PurchasedItem
from payments.models import BasePayment
from payments.signals import status_changed

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


@receiver(status_changed)
def change_payment_status(sender, *args, **kwargs):
    payment = kwargs['instance']
    order = payment.order
    if payment.status == 'confirmed':
        order.complete_order()
