import json
import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse

from payments import PurchasedItem, PaymentStatus
from payments.models import BasePayment
from payments.signals import status_changed

from plans.signals import account_automatic_renewal
from plans.models import Order

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

    def get_user(self):
        return self.order.user

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
            price=self.order.total(),
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
        self.order.user.userplan.set_plan_renewal(
            order=self.order,
            token=token,
            payment_provider=self.variant,
            card_expire_year=card_expire_year,
            card_expire_month=card_expire_month,
            has_automatic_renewal=True,
        )


@receiver(status_changed)
def change_payment_status(sender, *args, **kwargs):
    payment = kwargs['instance']
    order = payment.order
    if payment.status == PaymentStatus.CONFIRMED:
        order.complete_order()
    if (
            order.status != Order.STATUS.COMPLETED and
            payment.status not in (PaymentStatus.CONFIRMED, PaymentStatus.WAITING)
    ):
        order.status = Order.STATUS.CANCELED
        order.save()


@receiver(account_automatic_renewal)
def renew_accounts(sender, user, *args, **kwargs):
    userplan = user.userplan
    if userplan.recurring.has_automatic_renewal:
        order = userplan.recurring.create_renew_order()

        payment = create_payment_object(userplan.recurring.payment_provider, order)
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
        if payment.status == 'confirmed':
            order.complete_order()
