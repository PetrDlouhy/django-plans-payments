import json
import logging
import warnings
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.dispatch.dispatcher import receiver
from django.urls import reverse
from payments import PaymentStatus, PurchasedItem, RedirectNeeded, WalletStatus
from payments.models import BasePayment, BaseWallet
from payments.signals import status_changed
from plans.base.models import AbstractRecurringUserPlan
from plans.contrib import get_user_language, send_template_email
from plans.models import Order
from plans.signals import account_automatic_renewal
from swapper import swappable_setting

from .signals import renew_token_invalidated
from .views import create_payment_object

logger = logging.getLogger(__name__)


class RecurringUserPlan(AbstractRecurringUserPlan, BaseWallet):
    """
    RecurringUserPlan that inherits from BaseWallet.

    Bridges django-plans (subscription) with django-payments (payment processing)
    by implementing both interfaces in the connector layer.

    Provides:
    - token (from both parents - same field, perfect!)
    - status (from BaseWallet)
    - extra_data (from BaseWallet) - stores customer_id, etc.
    - All subscription fields (from AbstractRecurringUserPlan)
    """

    # Override ForeignKeys to use fully qualified references to resolve in plans app
    user_plan: models.OneToOneField = models.OneToOneField(
        "plans.UserPlan", on_delete=models.CASCADE, related_name="recurring"
    )
    pricing: models.ForeignKey = models.ForeignKey(
        "plans.Pricing",
        help_text="Recurring pricing",
        default=None,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    class Meta(AbstractRecurringUserPlan.Meta):
        abstract = False
        app_label = "plans_payments"
        # The swappable system will handle model registration
        swappable = swappable_setting("plans", "RecurringUserPlan")
        # When model is swapped, use the existing table name from plans app
        # This handles the case where django-plans migrations already created the table
        db_table = "plans_recurringuserplan"

    def payment_completed(self, payment):
        """Called after wallet payment attempt.

        A CONFIRMED payment activates the wallet and marks the token
        verified. Failed payments leave the wallet untouched - a transient
        decline must not disarm automatic renewals; permanently dead tokens
        are handled by Payment.invalidate_renew_token() instead.
        """
        if payment.status == PaymentStatus.CONFIRMED:
            self.status = WalletStatus.ACTIVE
            self.token_verified = True
            self.save(update_fields=["status", "token_verified"])


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

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "transaction_id"]),
        ]

    def save(self, **kwargs):
        if "payu" in self.variant:
            # TODO: base this on actual payment methods and currency fees on PayU
            # or even better on real PayU info
            self.transaction_fee = self.total * Decimal("0.029") + Decimal("0.05")
        elif "stripe" in self.variant:
            # Extract Stripe fee from attrs (set by django-payments StripeProviderV3)
            if hasattr(self, "attrs") and hasattr(self.attrs, "stripe_fee"):
                stripe_fee = self.attrs.stripe_fee
                if stripe_fee is not None:
                    # Stripe fee is in cents, convert to currency units
                    self.transaction_fee = Decimal(stripe_fee) / Decimal("100")
        elif hasattr(self, "extra_data") and self.extra_data:
            extra_data = json.loads(self.extra_data)
            if "response" in extra_data:
                transaction_fee_missing = False
                try:
                    transactions = extra_data["response"]["transactions"]
                except KeyError:
                    transaction_fee_missing = self.transaction_fee == 0
                else:
                    for transaction in transactions:
                        related_resources = transaction["related_resources"]
                        if len(related_resources) == 1:
                            sale = related_resources[0]["sale"]
                            if "transaction_fee" in sale:
                                self.transaction_fee = Decimal(
                                    sale["transaction_fee"]["value"]
                                )
                            else:
                                transaction_fee_missing = True
                if transaction_fee_missing:
                    logger.warning(
                        "Payment fee not included", extra={"extra_data": extra_data}
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

    def invalidate_renew_token(self):
        """Mark the stored recurring token as unusable.

        Called by payment providers (e.g. django-payments-payu) when the
        gateway reports a permanent token error - retrying it can never
        succeed. The token is marked unverified so renewal tasks stop
        selecting the account and get_renew_token() returns None; the card
        metadata is kept for the UI. Sends renew_token_invalidated so host
        apps can prompt the user to update their payment method.
        """
        try:
            recurring_plan = self.order.user.userplan.recurring
        except ObjectDoesNotExist:
            return
        recurring_plan.token_verified = False
        recurring_plan.status = WalletStatus.ERASED
        recurring_plan.save()
        renew_token_invalidated.send(
            sender=self.__class__, payment=self, recurring_user_plan=recurring_plan
        )

    def get_renew_data(self):
        """
        Get token + extra_data from RecurringUserPlan (which IS a wallet).

        Returns dict with token and provider-specific data from extra_data.
        """
        try:
            recurring = self.order.user.userplan.recurring
            if not (
                recurring.token_verified
                and recurring.status == WalletStatus.ACTIVE
                and self.variant == recurring.payment_provider
            ):
                return None

            data = {"token": recurring.token}
            # Add provider-specific data from extra_data (e.g., customer_id for Stripe)
            if recurring.extra_data:
                if not isinstance(recurring.extra_data, dict):
                    raise ValueError(
                        f"extra_data must be dict, got {type(recurring.extra_data)}"
                    )
                data.update(recurring.extra_data)
            return data

        except ObjectDoesNotExist:
            return None

    def set_renew_token(
        self,
        token,
        card_expire_year=None,
        card_expire_month=None,
        card_masked_number=None,
        **kwargs,
    ):
        """
        Store the recurring payments renew token for user of this payment
        The renew token is string defined by the provider
        """
        # Extract implementation-specific parameters
        automatic_renewal = kwargs.get("automatic_renewal")
        renewal_triggered_by = kwargs.get("renewal_triggered_by")

        # Handle defaults and deprecation
        if automatic_renewal is None and renewal_triggered_by is None:
            automatic_renewal = True
        if automatic_renewal is not None:
            warnings.warn(
                "automatic_renewal is deprecated. Use renewal_triggered_by instead.",
                DeprecationWarning,
            )
        if renewal_triggered_by == "user":
            renewal_triggered_by = AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.USER
        elif renewal_triggered_by == "task":
            renewal_triggered_by = AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK
        elif renewal_triggered_by == "other":
            renewal_triggered_by = AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.OTHER
        elif renewal_triggered_by is None:
            warnings.warn(
                "renewal_triggered_by=None is deprecated. "
                "Set an AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY instead.",
                DeprecationWarning,
            )
            renewal_triggered_by = (
                AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK
                if automatic_renewal
                else AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.USER
            )
        else:
            raise ValueError(f"Invalid renewal_triggered_by: {renewal_triggered_by}")

        # set_plan_renewal creates or updates the RecurringUserPlan: it
        # resets the subscription fields ("don't mix old and new values"),
        # applies the new ones, saves, and returns the instance. Doing the
        # wallet-field updates on the instance it returns avoids clobbering
        # them with a stale full-row save.
        recurring = self.order.user.userplan.set_plan_renewal(
            order=self.order,
            token=token,
            payment_provider=self.variant,
            card_expire_year=card_expire_year,
            card_expire_month=card_expire_month,
            card_masked_number=card_masked_number,
            renewal_triggered_by=renewal_triggered_by,
        )

        # Wallet fields: a fresh token starts unproven - payment_completed()
        # activates the wallet on the first CONFIRMED payment. extra_data is
        # reset to the provider-specific kwargs (e.g. Stripe customer_id),
        # matching the reset semantics of set_plan_renewal.
        processed_keys = {"automatic_renewal", "renewal_triggered_by"}
        recurring.status = WalletStatus.PENDING
        recurring.extra_data = {
            key: value for key, value in kwargs.items() if key not in processed_keys
        }
        recurring.save(update_fields=["status", "extra_data"])


@receiver(status_changed, sender=Payment)
def change_payment_status(sender, *args, **kwargs):
    payment = kwargs["instance"]
    order = payment.order
    if payment.status == PaymentStatus.CONFIRMED:
        if hasattr(order.user.userplan, "recurring"):
            # RecurringUserPlan IS a wallet, so use payment_completed method
            order.user.userplan.recurring.payment_completed(payment)
        order.complete_order()
    if (
        getattr(settings, "PLANS_PAYMENTS_RETURN_ORDER_WHEN_PAYMENT_REFUNDED", False)
        and payment.status == PaymentStatus.REFUNDED
    ):
        order._change_reason = (
            f"Django-plans-payments: Payment status changed to {payment.status}"
        )
        order.return_order()
    elif order.status != Order.STATUS.COMPLETED and payment.status not in (
        PaymentStatus.CONFIRMED,
        PaymentStatus.WAITING,
        PaymentStatus.INPUT,
    ):
        order.status = Order.STATUS.CANCELED
        # In case django-simples-history is installed
        order._change_reason = (
            f"Django-plans-payments: Payment status changed to {payment.status}"
        )
        order.save()
        # Maybe we would like to re-enable this for payments statuses that will not be ever renewed
        # (like "SAC - Account closed (do not try again)" on PayU)
        # if hasattr(order.user.userplan, "recurring"):
        #     order.user.userplan.recurring.token_verified = False
        #     order.user.userplan.recurring.save()


@receiver(account_automatic_renewal)
def renew_accounts(sender, user, *args, **kwargs):
    userplan = user.userplan
    if (
        userplan.recurring.payment_provider in settings.PAYMENT_VARIANTS
        and userplan.recurring.renewal_triggered_by
        == AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK
    ):
        order = userplan.recurring.create_renew_order()

        payment = create_payment_object(
            userplan.recurring.payment_provider, order, autorenewed_payment=True
        )

        try:
            payment.autocomplete_with_wallet()
        except RedirectNeeded as redirect_to:
            print("CVV2/3DS code is required, enter it at %s" % str(redirect_to))
            send_template_email(
                [payment.order.user.email],
                "mail/renew_cvv_3ds_title.txt",
                "mail/renew_cvv_3ds_body.txt",
                {
                    "redirect_url": str(redirect_to),
                    "user": user,
                    "userplan": userplan,
                },
                get_user_language(payment.order.user),
            )
        if payment.status == PaymentStatus.CONFIRMED:
            order.complete_order()
