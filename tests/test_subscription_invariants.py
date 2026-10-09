"""Buying something never ends or rewrites the buyer's subscription.

A payment changes the subscription (RecurringUserPlan) only when it is confirmed
with a new renew token. 2.4.0 broke that: a confirmed one-off card payment
("payu" against a "payu-recurring" subscription) deleted the subscription. These
tests run every payment status through payment creation and the status change,
with the subscription's own variant and with another one, on regular and on
plan-change orders, so a status or a code path added later is covered too.
"""

import itertools
from decimal import Decimal

from django.test import TestCase
from model_bakery import baker
from payments import PaymentStatus
from plans.models import Order, RecurringUserPlan

from plans_payments.views import create_payment_object

STATUSES = [status for status, _ in PaymentStatus.CHOICES]
SUBSCRIPTION_VARIANT = "subscription-variant"


class PaymentsKeepTheSubscriptionTests(TestCase):
    def arm_subscription(self, plan_change):
        order = baker.make(
            "Order",
            status=Order.STATUS.NEW,
            amount=Decimal("10"),
            tax=0,
            currency="EUR",
            pricing=None if plan_change else baker.make("Pricing"),
        )
        userplan = baker.make("UserPlan", user=order.user)
        recurring = baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            payment_provider=SUBSCRIPTION_VARIANT,
            token="stored-token",
            token_verified=True,
        )
        return order, recurring

    def test_no_payment_ends_or_rewrites_the_subscription(self):
        for status, variant, plan_change in itertools.product(
            STATUSES, ("default", SUBSCRIPTION_VARIANT), (False, True)
        ):
            with self.subTest(status=status, variant=variant, plan_change=plan_change):
                order, recurring = self.arm_subscription(plan_change)

                payment = create_payment_object(variant, order)
                payment.change_status(status)

                kept = RecurringUserPlan.objects.filter(pk=recurring.pk).first()
                self.assertIsNotNone(kept, "the payment deleted the subscription")
                self.assertEqual(
                    (kept.payment_provider, kept.token, kept.token_verified),
                    (SUBSCRIPTION_VARIANT, "stored-token", True),
                )

    def test_a_confirmed_payment_with_a_new_token_is_the_one_that_changes_it(self):
        """The counterpart: storing a new renew token is how a subscription moves."""
        order, recurring = self.arm_subscription(plan_change=False)
        payment = create_payment_object("default", order, replace_renew_token=True)
        payment.set_renew_token("new-token", renewal_triggered_by="task")

        payment.change_status(PaymentStatus.CONFIRMED)

        recurring.refresh_from_db()
        self.assertEqual(
            (recurring.payment_provider, recurring.token, recurring.token_verified),
            ("default", "new-token", True),
        )
