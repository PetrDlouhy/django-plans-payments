import json
import logging
from decimal import Decimal
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse
from payments import PaymentStatus, PurchasedItem
from payments.core import get_base_url
from payments.models import BasePayment
from payments.signals import status_changed
from plans.contrib import get_user_language, send_template_email
from plans.models import Order
from plans.signals import account_automatic_renewal

from .views import create_payment_object

logger = logging.getLogger(__name__)


class Payment(BasePayment):
    order: Order = models.ForeignKey(
        "plans.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    transaction_fee: models.DecimalField = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal("0.0"),
    )
    autorenewed_payment: models.BooleanField = models.BooleanField(
        default=False,
    )

    def clean(self):
        if self.order.status == Order.STATUS.COMPLETED:
            confirmed_payment_count = self.order.payment_set.exclude(pk=self.pk)
            confirmed_payment_count = confirmed_payment_count.filter(
                status=PaymentStatus.CONFIRMED
            ).count()
            if self.status != PaymentStatus.CONFIRMED and confirmed_payment_count == 0:
                raise ValidationError(
                    {
                        "status": "Can't leave confirmed order without any confirmed payment. "
                        "Please change Order first if you still want to perform this change.",
                    },
                )

    def save(self, **kwargs):
        if "payu" in self.variant:
            # TODO: base this on actual payment methods and currency fees on PayU
            # or even better on real PayU info
            self.transaction_fee = self.total * Decimal("0.029") + Decimal("0.05")
        elif hasattr(self, "extra_data") and self.extra_data:
            extra_data = json.loads(self.extra_data)
            if "response" in extra_data:
                transactions = extra_data["response"]["transactions"]
                for transaction in transactions:
                    related_resources = transaction["related_resources"]
                    if len(related_resources) == 1:
                        sale = related_resources[0]["sale"]
                        if "transaction_fee" in sale:
                            self.transaction_fee += Decimal(
                                sale["transaction_fee"]["value"]
                            )
                        else:
                            logger.warning(
                                "Payment fee not included",
                                extra={
                                    "extra_data": extra_data,
                                },
                            )
        ret_val = super().save(**kwargs)
        return ret_val

    def get_failure_url(self):
        return reverse("order_payment_failure", kwargs={"pk": self.order.pk})

    def get_success_url(self):
        return reverse("order_payment_success", kwargs={"pk": self.order.pk})

    def get_payment_url(self):
        return reverse("payment_details", kwargs={"payment_id": self.pk})

    def get_purchased_items(self):
        yield PurchasedItem(
            name=self.description,
            sku=self.order.pk,
            quantity=1,
            price=self.order.amount,
            tax_rate=(1 + self.order.tax / 100) if self.order.tax else 1,
            currency=self.currency,
        )

    def get_renew_token(self):
        """
        Get the recurring payments renew token for user of this payment
        Used by PayU provider for now
        """
        try:
            recurring_plan = self.order.user.userplan.recurring
            if (
                recurring_plan.token_verified
                and self.variant == recurring_plan.payment_provider
            ):
                return recurring_plan.token
        except ObjectDoesNotExist:
            pass
        return None

    def set_renew_token(
        self,
        token,
        card_expire_year=None,
        card_expire_month=None,
        card_masked_number=None,
        automatic_renewal=True,
    ):
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
            card_masked_number=card_masked_number,
            has_automatic_renewal=automatic_renewal,
        )


@receiver(status_changed)
def change_payment_status(sender, *args, **kwargs):
    payment = kwargs["instance"]
    order = payment.order
    if payment.status == PaymentStatus.CONFIRMED:
        if hasattr(order.user.userplan, "recurring"):
            order.user.userplan.recurring.token_verified = True
            order.user.userplan.recurring.save()
        order.complete_order()
    if order.status != Order.STATUS.COMPLETED and payment.status not in (
        PaymentStatus.CONFIRMED,
        PaymentStatus.WAITING,
        PaymentStatus.INPUT,
    ):
        order.status = Order.STATUS.CANCELED
        order.save()
        if hasattr(order.user.userplan, "recurring"):
            order.user.userplan.recurring.token_verified = False
            order.user.userplan.recurring.save()


@receiver(account_automatic_renewal)
def renew_accounts(sender, user, *args, **kwargs):
    userplan = user.userplan
    if (
        userplan.recurring.payment_provider in settings.PAYMENT_VARIANTS
        and userplan.recurring.has_automatic_renewal
    ):
        order = userplan.recurring.create_renew_order()

        payment = create_payment_object(
            userplan.recurring.payment_provider, order, autorenewed_payment=True
        )

        try:
            redirect_url = payment.auto_complete_recurring()
        except Exception as e:
            print(f"Exceptin during automatic renewal: {e}")
            logger.exception(
                "Exception during account renewal",
                extra={
                    "payment": payment,
                },
            )
            redirect_url = urljoin(
                get_base_url(),
                reverse(
                    "create_order_plan", kwargs={"pk": order.get_plan_pricing().pk}
                ),
            )

        if redirect_url != "success":
            print("CVV2/3DS code is required, enter it at %s" % redirect_url)
            send_template_email(
                [payment.order.user.email],
                "mail/renew_cvv_3ds_title.txt",
                "mail/renew_cvv_3ds_body.txt",
                {"redirect_url": redirect_url},
                get_user_language(payment.order.user),
            )
        if payment.status == PaymentStatus.CONFIRMED:
            order.complete_order()
