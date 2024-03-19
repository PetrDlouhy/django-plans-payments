#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_django-plans-payments
------------

Tests for `django-plans-payments` models module.
"""
import json
from datetime import datetime
from decimal import Decimal

import pytz
from django.test import TestCase
from freezegun import freeze_time
from model_bakery import baker
from payments import PaymentStatus
from plans.models import Invoice, Order

from plans_payments import models


class TestPlansPayments(TestCase):
    def setUp(self):
        pass

    def test_clean(self):
        p = models.Payment(order=baker.make("Order", status=Order.STATUS.NEW))
        p.clean()
        self.assertEqual(p.status, "waiting")

    def test_clean_completed(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.COMPLETED),
            status=PaymentStatus.CONFIRMED,
        )
        p.clean()
        self.assertEqual(p.status, "confirmed")

    def test_clean_completed_no_confirmed_payment(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.COMPLETED),
            status=PaymentStatus.WAITING,
        )
        with self.assertRaisesRegex(
            Exception, "Can't leave confirmed order without any confirmed payment."
        ):
            p.clean()
        self.assertEqual(p.status, "waiting")

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

    def test_set_renew_token(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user)
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
        self.assertEqual(userplan.recurring.has_automatic_renewal, True)

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

    def test_change_payment_status_refunded_order_not_valid(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NOT_VALID),
            status=PaymentStatus.REFUNDED,
        )
        baker.make("UserPlan", user=p.order.user)
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
        baker.make("RecurringUserPlan", user_plan=userplan)
        models.renew_accounts("sender", user, p)
        self.assertEqual(p.autorenewed_payment, False)

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
            has_automatic_renewal=True,
            amount=14,
            pricing=plan_pricing.pricing,
        )
        models.renew_accounts("sender", user, p)
        self.assertEqual(p.autorenewed_payment, False)

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
