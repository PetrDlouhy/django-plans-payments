from unittest import mock

from django.test import TestCase
from django.urls import reverse
from model_bakery import baker
from payments import PaymentStatus, RedirectNeeded

from plans_payments.models import Payment
from plans_payments.views import create_payment_object


class PaymentDetailsViewTests(TestCase):
    def test_payment_details_view_get_anonymous(self):
        response = self.client.get(reverse("payment_details", kwargs={"payment_id": 1}))
        self.assertRedirects(response, "/login/?next=/payment_details/1/")

    def test_payment_details_view_get(self):
        user = baker.make("User")
        payment = baker.make(
            Payment, order__user=user, variant="default", billing_email="bar@baz.cz"
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("payment_details", kwargs={"payment_id": payment.id})
        )
        self.assertEqual(response.status_code, 200)
        # Build the expected options from PaymentStatus.CHOICES so the test
        # keeps passing across django-payments versions (e.g. the addition
        # of the "cancelled" status).
        status_options = "".join(
            f'<option value="{value}">{label}</option>'
            for value, label in PaymentStatus.CHOICES
        )
        self.assertContains(
            response,
            f'<select name="status" id="id_status">{status_options}</select>',
            html=True,
        )

    def test_payment_details_view_get_different_user(self):
        user = baker.make("User")
        payment = baker.make(
            Payment, order__user=user, variant="default", billing_email="bar@baz.cz"
        )
        self.client.force_login(baker.make("User"))
        response = self.client.get(
            reverse("payment_details", kwargs={"payment_id": payment.id})
        )
        self.assertEqual(response.status_code, 404)


class CreatePaymentViewTests(TestCase):
    def test_create_payment_view_get_anonymous(self):
        user = baker.make("User")
        order = baker.make("Order", user=user)
        response = self.client.get(
            reverse(
                "create_payment",
                kwargs={"order_id": order.id, "payment_variant": "default"},
            )
        )
        self.assertRedirects(
            response, f"/login/?next=/create_payment/default/{order.id}/"
        )

    def test_create_payment_view_get(self):
        user = baker.make("User")
        self.client.force_login(user)
        order = baker.make("Order", user=user)
        baker.make("UserPlan", user=user)
        baker.make("BillingInfo", user=user)
        response = self.client.get(
            reverse(
                "create_payment",
                kwargs={"order_id": order.id, "payment_variant": "default"},
            )
        )
        self.assertRedirects(
            response, reverse("payment_details", kwargs={"payment_id": 1})
        )
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, "input")
        self.assertEqual(payment.variant, "default")
        self.assertEqual(payment.billing_email, user.email)

    def test_create_payment_view_get_different_user(self):
        user = baker.make("User")
        self.client.force_login(baker.make("User"))
        order = baker.make("Order", user=user)
        response = self.client.get(
            reverse(
                "create_payment",
                kwargs={"order_id": order.id, "payment_variant": "default"},
            )
        )
        self.assertEqual(response.status_code, 404)


class PaymentDetailViewRedirectTests(TestCase):
    def test_payment_details_view_redirect_needed(self):
        """3-D Secure / CVV flow: get_form raising RedirectNeeded redirects."""
        user = baker.make("User")
        payment = baker.make(
            Payment, order__user=user, variant="default", billing_email="bar@baz.cz"
        )
        self.client.force_login(user)
        with mock.patch.object(
            Payment, "get_form", side_effect=RedirectNeeded("https://3ds.example.com")
        ):
            response = self.client.get(
                reverse("payment_details", kwargs={"payment_id": payment.id})
            )
        self.assertRedirects(
            response, "https://3ds.example.com", fetch_redirect_response=False
        )


class CreatePaymentObjectTests(TestCase):
    def test_create_payment_object_deletes_foreign_recurring(self):
        """A recurring plan from another provider is dropped on new payment."""
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        baker.make(
            "RecurringUserPlan",
            user_plan=userplan,
            payment_provider="other-variant",
        )
        order = baker.make("Order", user=user, amount=10, tax=0, currency="EUR")
        baker.make("BillingInfo", user=user)
        payment = create_payment_object("default", order)
        self.assertEqual(payment.variant, "default")
        userplan.refresh_from_db()
        self.assertFalse(hasattr(userplan, "recurring"))


class AdminSmokeTests(TestCase):
    def test_payment_admin_instantiates(self):
        from django.contrib.admin.sites import AdminSite

        from plans_payments.admin import PaymentAdmin

        payment_admin = PaymentAdmin(Payment, AdminSite())
        self.assertIn("status", payment_admin.list_display)
