from unittest import mock

from django.core.checks import run_checks
from django.test import SimpleTestCase


class WalletSupportCheckTests(SimpleTestCase):
    def test_silent_with_a_wallet_capable_django_payments(self):
        self.assertEqual([m for m in run_checks() if m.id == "plans_payments.W001"], [])

    def test_warns_when_payments_cannot_charge_a_stored_card(self):
        without_wallet = type("Payment", (), {})
        with mock.patch("plans_payments.checks.get_payment_model", return_value=without_wallet):
            messages = [m for m in run_checks() if m.id == "plans_payments.W001"]
        self.assertEqual(len(messages), 1)
        self.assertIn("autocomplete_with_wallet", messages[0].msg)
