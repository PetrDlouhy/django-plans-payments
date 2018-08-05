from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse

from payments import PurchasedItem
from payments.models import BasePayment
from payments.signals import status_changed


class Payment(BasePayment):
    order = models.ForeignKey(
        'plans.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def get_failure_url(self):
        return reverse('order_payment_failure', kwargs={'pk': self.order.pk})

    def get_success_url(self):
        return reverse('order_payment_success', kwargs={'pk': self.order.pk})

    def get_purchased_items(self):
        yield PurchasedItem(
            name=self.order.__str__(),
            sku='BSKV',
            quantity=1,
            price=self.order.amount,
            currency=self.order.currency,
            # tax=self.order.tax,
        )


@receiver(status_changed)
def change_payment_status(sender, *args, **kwargs):
    payment = kwargs['instance']
    order = payment.order
    if payment.status == 'confirmed':
        order.complete_order()
