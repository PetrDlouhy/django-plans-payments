#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_django-plans-payments
------------

Tests for `django-plans-payments` models module.
"""
import json
import warnings
from datetime import datetime
from decimal import Decimal

import pytz
from django.test import TestCase, override_settings
from freezegun import freeze_time
from model_bakery import baker
from payments import PaymentStatus
from plans.models import Invoice, Order, RecurringUserPlan

from plans_payments import models


class TestPlansPayments(TestCase):
    def setUp(self):
        pass

    def test_save(self):
        p = models.Payment(transaction_fee=1)
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, 1)

    def test_save_extra_data(self):
        p = models.Payment()
        extra_data = {
            "response": {
                "transactions": (
                    {
                        "related_resources": (
                            {
                                "sale": {
                                    "transaction_fee": {
                                        "value": "5.2",
                                    },
                                },
                            },
                        ),
                    },
                ),
            },
        }
        p.extra_data = json.dumps(extra_data)
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("5.20"))

    def test_save_extra_data_without_fee(self):
        p = models.Payment()
        extra_data = {
            "response": {
                "transactions": (
                    {
                        "related_resources": (
                            {
                                "sale": {},
                            },
                        ),
                    },
                ),
            },
        }
        p.extra_data = json.dumps(extra_data)
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("0.0"))

    def test_save_payu(self):
        """Save with payment varian payu"""
        p = models.Payment(variant="payu", total=Decimal("10.00"))
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("0.34"))

    def test_double_save_paypal(self):
        """
        Save with payment varian paypal
        multiple saves should not reult in double transaction_fee value
        """
        extra_data = {
            "response": {
                "transactions": (
                    {
                        "related_resources": (
                            {
                                "sale": {
                                    "transaction_fee": {
                                        "value": "0.34",
                                    },
                                },
                            },
                        ),
                    },
                ),
            },
        }
        p = models.Payment(
            variant="paypal", total=Decimal("10.00"), extra_data=json.dumps(extra_data)
        )
        p.save()
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("0.34"))

    def test_save_no_extra_data(self):
        p = models.Payment()
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("0.0"))

    def test_save_extra_data_no_response(self):
        p = models.Payment()
        extra_data = {}
        p.extra_data = json.dumps(extra_data)
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("0.0"))

    def test_save_extra_data_no_related_resources(self):
        p = models.Payment()
        extra_data = {
            "response": {
                "transactions": (
                    {
                        "related_resources": (),
                    },
                ),
            },
        }
        p.extra_data = json.dumps(extra_data)
        p.save()
        rp = models.Payment.objects.get()
        self.assertEqual(rp.transaction_fee, Decimal("0.0"))

    def test_save_extra_data_no_transactions(self):
        p = models.Payment()
        p.transaction_fee = Decimal("0.34")
        p.extra_data = json.dumps({"response": {"foo": "bar"}})

        # TODO: In Python 3.10+: Replace with assertNoLogs
        with self.assertRaisesRegex(
            AssertionError,
            r"^no logs of level DEBUG or higher triggered on plans_payments.models$",
        ):
            with self.assertLogs(logger="plans_payments.models", level="DEBUG"):
                p.save()

        self.assertEqual(
            models.Payment.objects.values_list("transaction_fee", flat=True).get(),
            Decimal("0.34"),
        )

    def test_save_extra_data_no_transactions_no_transaction_fee(self):
        p = models.Payment()
        p.extra_data = json.dumps({"response": {"foo": "bar"}})

        with self.assertLogs(logger="plans_payments.models", level="WARNING") as logs:
            p.save()

        self.assertIn(
            "WARNING:plans_payments.models:Payment fee not included", logs.output
        )
        self.assertFalse(
            models.Payment.objects.values_list("transaction_fee", flat=True).get()
        )

    def tearDown(self):
        pass

    def test_get_renew_token(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        self.assertEqual(p.get_renew_token(), None)

    def test_get_renew_token_verified(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user), variant="default")
        userplan = baker.make("UserPlan", user=user, order__user=user)
        baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            token_verified=True,
            token="token",
            payment_provider="default",
        )
        self.assertEqual(p.get_renew_token(), "token")

    def test_set_renew_token_task(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user)
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            p.set_renew_token(
                "token",
                card_expire_year=2020,
                card_expire_month=12,
                card_masked_number="1234",
                renewal_triggered_by="task",
            )
        self.assertEqual(userplan.recurring.token, "token")
        self.assertEqual(userplan.recurring.card_expire_year, 2020)
        self.assertEqual(userplan.recurring.card_expire_month, 12)
        self.assertEqual(userplan.recurring.card_masked_number, "1234")
        self.assertEqual(
            userplan.recurring.renewal_triggered_by,
            RecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
        )
        self.assertFalse(caught_warnings)

    def test_set_renew_token_other(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user)
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            p.set_renew_token(
                "token",
                card_expire_year=2020,
                card_expire_month=12,
                card_masked_number="1234",
                renewal_triggered_by="other",
            )
        self.assertEqual(userplan.recurring.token, "token")
        self.assertEqual(userplan.recurring.card_expire_year, 2020)
        self.assertEqual(userplan.recurring.card_expire_month, 12)
        self.assertEqual(userplan.recurring.card_masked_number, "1234")
        self.assertEqual(
            userplan.recurring.renewal_triggered_by,
            RecurringUserPlan.RENEWAL_TRIGGERED_BY.OTHER,
        )
        self.assertFalse(caught_warnings)

    def test_set_renew_token_user(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user)
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            p.set_renew_token(
                "token",
                card_expire_year=2020,
                card_expire_month=12,
                card_masked_number="1234",
                renewal_triggered_by="user",
            )
        self.assertEqual(userplan.recurring.token, "token")
        self.assertEqual(userplan.recurring.card_expire_year, 2020)
        self.assertEqual(userplan.recurring.card_expire_month, 12)
        self.assertEqual(userplan.recurring.card_masked_number, "1234")
        self.assertEqual(
            userplan.recurring.renewal_triggered_by,
            RecurringUserPlan.RENEWAL_TRIGGERED_BY.USER,
        )
        self.assertFalse(caught_warnings)

    def test_set_renew_token_none_automatic_renewal_true(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user)
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            p.set_renew_token(
                "token",
                card_expire_year=2020,
                card_expire_month=12,
                card_masked_number="1234",
                automatic_renewal=True,
            )
        self.assertEqual(userplan.recurring.token, "token")
        self.assertEqual(userplan.recurring.card_expire_year, 2020)
        self.assertEqual(userplan.recurring.card_expire_month, 12)
        self.assertEqual(userplan.recurring.card_masked_number, "1234")
        self.assertEqual(
            userplan.recurring.renewal_triggered_by,
            RecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
        )
        self.assertEqual(len(caught_warnings), 2)
        self.assertTrue(issubclass(caught_warnings[0].category, DeprecationWarning))
        self.assertEqual(
            str(caught_warnings[0].message),
            "automatic_renewal is deprecated. Use renewal_triggered_by instead.",
        )
        self.assertTrue(issubclass(caught_warnings[1].category, DeprecationWarning))
        self.assertEqual(
            str(caught_warnings[1].message),
            "renewal_triggered_by=None is deprecated. Set an AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY instead.",
        )

    def test_set_renew_token_none_automatic_renewal_false(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user)
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            p.set_renew_token(
                "token",
                card_expire_year=2020,
                card_expire_month=12,
                card_masked_number="1234",
                automatic_renewal=False,
            )
        self.assertEqual(userplan.recurring.token, "token")
        self.assertEqual(userplan.recurring.card_expire_year, 2020)
        self.assertEqual(userplan.recurring.card_expire_month, 12)
        self.assertEqual(userplan.recurring.card_masked_number, "1234")
        self.assertEqual(
            userplan.recurring.renewal_triggered_by,
            RecurringUserPlan.RENEWAL_TRIGGERED_BY.USER,
        )
        self.assertEqual(len(caught_warnings), 2)
        self.assertTrue(issubclass(caught_warnings[0].category, DeprecationWarning))
        self.assertEqual(
            str(caught_warnings[0].message),
            "automatic_renewal is deprecated. Use renewal_triggered_by instead.",
        )
        self.assertTrue(issubclass(caught_warnings[1].category, DeprecationWarning))
        self.assertEqual(
            str(caught_warnings[1].message),
            "renewal_triggered_by=None is deprecated. Set an AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY instead.",
        )

    def test_change_payment_status(self):
        p = models.Payment(order=baker.make("Order", status=Order.STATUS.NEW))
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "waiting")
        self.assertEqual(p.order.status, Order.STATUS.NEW)

    def test_change_payment_status_confirmed(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NEW),
            status=PaymentStatus.CONFIRMED,
        )
        userplan = baker.make("UserPlan", user=p.order.user)
        recurring_user_plan = baker.make("RecurringUserPlan", user_plan=userplan)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "confirmed")
        self.assertEqual(recurring_user_plan.token_verified, True)
        self.assertEqual(p.order.status, Order.STATUS.COMPLETED)

    @freeze_time("2018-01-01")
    def test_change_payment_status_confirmed_double_submit(self):
        """Test double submit of payment status_changed signal"""
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NEW),
            status=PaymentStatus.CONFIRMED,
        )
        userplan = baker.make("UserPlan", user=p.order.user)
        baker.make("BillingInfo", user=p.order.user)
        baker.make("RecurringUserPlan", user_plan=userplan)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.order.completed, datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC))

        # Switch order back to new to simulate concurrent double submit
        p.status = PaymentStatus.REJECTED

        with freeze_time("2018-01-02"):
            models.change_payment_status("sender", instance=p)
        self.assertEqual(p.order.completed, datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC))
        # Only one Invoice was created
        self.assertEqual(Invoice.objects.count(), 1)

    def test_change_payment_status_rejected(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NEW),
            status=PaymentStatus.REJECTED,
        )
        userplan = baker.make("UserPlan", user=p.order.user)
        baker.make("RecurringUserPlan", user_plan=userplan)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "rejected")
        self.assertEqual(p.order.status, Order.STATUS.CANCELED)

    def test_change_payment_status_rejected_order_completed(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.COMPLETED),
            status=PaymentStatus.REJECTED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "rejected")
        self.assertEqual(p.order.status, Order.STATUS.COMPLETED)

    def test_change_payment_status_refunded(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.COMPLETED),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "refunded")
        self.assertEqual(p.order.status, Order.STATUS.COMPLETED)

    @override_settings(PLANS_PAYMENTS_RETURN_ORDER_WHEN_PAYMENT_REFUNDED=True)
    def test_change_payment_status_refunded_return_enabled(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.COMPLETED),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "refunded")
        self.assertEqual(p.order.status, Order.STATUS.RETURNED)

    def test_change_payment_status_refunded_order_not_valid(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NOT_VALID),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "refunded")
        self.assertEqual(p.order.status, Order.STATUS.CANCELED)

    @override_settings(PLANS_PAYMENTS_RETURN_ORDER_WHEN_PAYMENT_REFUNDED=True)
    def test_change_payment_status_refunded_order_not_valid_return_enabled(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NOT_VALID),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "refunded")
        self.assertEqual(p.order.status, Order.STATUS.RETURNED)

    # This should not happen practically but with Django Admin, anything can happen...
    def test_change_payment_status_refunded_order_canceled(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.CANCELED),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "refunded")
        self.assertEqual(p.order.status, Order.STATUS.CANCELED)

    # This should not happen practically but with Django Admin, anything can happen...
    @override_settings(PLANS_PAYMENTS_RETURN_ORDER_WHEN_PAYMENT_REFUNDED=True)
    def test_change_payment_status_refunded_order_canceled_return_enabled(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.CANCELED),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
        with self.assertRaisesRegex(
            ValueError,
            r"^Cannot return order with status other than COMPLETED and NOT_VALID: 4$",
        ):
            models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "refunded")
        self.assertEqual(p.order.status, Order.STATUS.CANCELED)

    def test_change_payment_status_confirmed_no_recurring(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NEW),
            status=PaymentStatus.CONFIRMED,
        )
        baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "confirmed")
        self.assertEqual(p.order.status, Order.STATUS.COMPLETED)

    def test_renew_accounts_no_variant(self):
        p = models.Payment()
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            renewal_triggered_by=RecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
        )
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            models.renew_accounts("sender", user, p)
        self.assertEqual(p.autorenewed_payment, False)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(models.Payment.objects.exclude(id=p.id).exists())
        self.assertFalse(caught_warnings)

    def test_renew_accounts(self):
        p = baker.make("Payment", variant="default", order__amount=12)
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        plan_pricing = baker.make("PlanPricing", plan=userplan.plan, price=12)
        baker.make("BillingInfo", user=user)
        baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            payment_provider="default",
            renewal_triggered_by=RecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            amount=14,
            pricing=plan_pricing.pricing,
        )
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            models.renew_accounts("sender", user, p)
        (order_renewed,) = Order.objects.exclude(id=p.order.id)
        (payment_renewed,) = models.Payment.objects.exclude(id=p.id)
        self.assertEqual(p.autorenewed_payment, False)
        self.assertEqual(order_renewed.plan, plan_pricing.plan)
        self.assertEqual(order_renewed.pricing, plan_pricing.pricing)
        self.assertEqual(order_renewed.amount, Decimal(14))
        self.assertEqual(order_renewed.user, user)
        self.assertEqual(payment_renewed.order, order_renewed)
        self.assertEqual(payment_renewed.variant, "default")
        self.assertTrue(payment_renewed.autorenewed_payment)
        self.assertFalse(caught_warnings)

    def test_renew_accounts_user(self):
        p = models.Payment(variant="default")
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            payment_provider="default",
            renewal_triggered_by=RecurringUserPlan.RENEWAL_TRIGGERED_BY.USER,
        )
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            models.renew_accounts("sender", user, p)
        self.assertEqual(p.autorenewed_payment, False)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(models.Payment.objects.exclude(id=p.id).exists())
        self.assertFalse(caught_warnings)

    def test_renew_accounts_other(self):
        p = models.Payment(variant="default")
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            payment_provider="default",
            renewal_triggered_by=RecurringUserPlan.RENEWAL_TRIGGERED_BY.OTHER,
        )
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            models.renew_accounts("sender", user, p)
        self.assertEqual(p.autorenewed_payment, False)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(models.Payment.objects.exclude(id=p.id).exists())
        self.assertFalse(caught_warnings)

    def test_change_payment_status_called(self):
        """test that change_payment_status receiver is executed when Payment.change_status is called
        NOTE: directly patching `change_payment_status` receiver is not working
        in this case, so we just check that `Order.status` was changed to `canceled`
        """

        user = baker.make("User")
        baker.make("UserPlan", user=user)
        p = baker.make("Payment", variant="default", order__user=user)

        self.assertNotEqual(p.order, Order.STATUS.CANCELED)
        p.change_status(PaymentStatus.REJECTED)
        self.assertEqual(p.order.status, Order.STATUS.CANCELED)
