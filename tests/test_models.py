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

from plans_payments import models


class TestPlans_payments(TestCase):

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
                                "sale": {
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
        self.assertEqual(rp.transaction_fee, Decimal("0.0"))

    def tearDown(self):
        pass
