from django.db import models
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse

from payments import PurchasedItem
from payments.models import BasePayment


class Payment(BasePayment):
    order = models.ForeignKey(
        'plans.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def get_failure_url(self):
        return reverse('payment_failure')

    def get_success_url(self):
        return reverse('payment_success')

    def get_purchased_items(self):
        # you'll probably want to retrieve these from an associated order
        yield PurchasedItem(
            name=self.order.__str__(),
            sku='BSKV',
            quantity=1,
            price=self.order.amount,
            currency=self.order.currency,
            # tax=self.order.tax,
        )
