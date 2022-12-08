from django.test import TestCase
from django.urls import reverse
from model_bakery import baker

from plans_payments.models import Payment


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
        self.assertContains(
            response,
            '<select name="status" id="id_status">'
            '<option value="waiting">Waiting for confirmation</option>'
            '<option value="preauth">Pre-authorized</option>'
            '<option value="confirmed">Confirmed</option>'
            '<option value="rejected">Rejected</option>'
            '<option value="refunded">Refunded</option>'
            '<option value="error">Error</option>'
            '<option value="input">Input</option>'
            "</select>",
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
