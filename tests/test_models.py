#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_django-plans-payments
------------

Tests for `django-plans-payments` models module.
"""
import json
from decimal import Decimal

from django.test import TestCase
from model_bakery import baker
from payments import PaymentStatus
from plans.models import Order

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

    def tearDown(self):
        pass

    def test_get_renew_token(self):
        user = baker.make("User")
        p = models.Payment(order=baker.make("Order", user=user))
        userplan = baker.make("UserPlan", user=user, order__user=user)
        baker.make("RecurringUserPlan", user_plan=userplan, token_verified=True)
        self.assertEqual(p.get_renew_token(), None)

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

    def test_change_payment_status_confirmed_no_recurring(self):
        p = models.Payment(
            order=baker.make("Order", status=Order.STATUS.NEW),
            status=PaymentStatus.CONFIRMED,
        )
        userplan = baker.make("UserPlan", user=p.order.user)
        models.change_payment_status("sender", instance=p)
        self.assertEqual(p.status, "confirmed")

    def test_renew_accounts(self):
        p = models.Payment()
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        baker.make("RecurringUserPlan", user_plan=userplan)
        models.renew_accounts("sender", user, p)
        self.assertEqual(p.autorenewed_payment, False)
