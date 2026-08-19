from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
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
        payment = baker.make(Payment, order__user=user, variant="default", billing_email="bar@baz.cz")
        self.client.force_login(user)
        response = self.client.get(reverse("payment_details", kwargs={"payment_id": payment.id}))
        self.assertEqual(response.status_code, 200)
        # Build the expected options from PaymentStatus.CHOICES so the test
        # keeps passing across django-payments versions (e.g. the addition
        # of the "cancelled" status).
        status_options = "".join(f'<option value="{value}">{label}</option>' for value, label in PaymentStatus.CHOICES)
        self.assertContains(
            response,
            f'<select name="status" id="id_status">{status_options}</select>',
            html=True,
        )

    def test_payment_details_view_get_different_user(self):
        user = baker.make("User")
        payment = baker.make(Payment, order__user=user, variant="default", billing_email="bar@baz.cz")
        self.client.force_login(baker.make("User"))
        response = self.client.get(reverse("payment_details", kwargs={"payment_id": payment.id}))
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
        self.assertRedirects(response, f"/login/?next=/create_payment/default/{order.id}/")

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
        self.assertRedirects(response, reverse("payment_details", kwargs={"payment_id": 1}))
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


class CreatePaymentIdempotencyGuardTests(TestCase):
    """The charge-attempt endpoint must be idempotent, not a machine gun.

    Users re-clicking through slow redirects and declines fire bursts of
    live charge attempts minutes apart; the worst pairs both capture, the
    rest trip the banks' anti-fraud. An attempt joins the one in flight,
    and an attempt right after a decline waits out a short cooldown.
    """

    def setUp(self):
        self.user = baker.make("User")
        baker.make("UserPlan", user=self.user)
        baker.make("BillingInfo", user=self.user)
        self.client.force_login(self.user)

    def _order(self):
        return baker.make("Order", user=self.user)

    def _create_payment_url(self, order):
        return reverse("create_payment", kwargs={"order_id": order.id, "payment_variant": "default"})

    def _existing_payment(self, order, status, age):
        payment = baker.make(Payment, order=order, variant="default", billing_email="bar@baz.cz", status=status)
        Payment.objects.filter(pk=payment.pk).update(created=timezone.now() - age)
        return payment

    def test_second_attempt_joins_the_payment_in_flight(self):
        order = self._order()
        in_flight = self._existing_payment(order, PaymentStatus.WAITING, age=timedelta(seconds=30))

        response = self.client.get(self._create_payment_url(order))

        self.assertEqual(Payment.objects.count(), 1)
        self.assertRedirects(
            response,
            reverse("payment_details", kwargs={"payment_id": in_flight.id}),
            fetch_redirect_response=False,
        )

    def test_attempt_on_a_new_order_joins_the_other_orders_payment_in_flight(self):
        # The burst shape seen in production: every click minted a NEW
        # order, so the guard must look across the user's orders.
        in_flight = self._existing_payment(self._order(), PaymentStatus.WAITING, age=timedelta(seconds=30))

        response = self.client.get(self._create_payment_url(self._order()))

        self.assertEqual(Payment.objects.count(), 1)
        self.assertRedirects(
            response,
            reverse("payment_details", kwargs={"payment_id": in_flight.id}),
            fetch_redirect_response=False,
        )

    def test_attempt_right_after_a_decline_waits(self):
        self._existing_payment(self._order(), PaymentStatus.REJECTED, age=timedelta(seconds=20))
        second_order = self._order()

        response = self.client.get(self._create_payment_url(second_order))

        self.assertEqual(Payment.objects.count(), 1)
        self.assertRedirects(
            response,
            reverse("order", kwargs={"pk": second_order.pk}),
            fetch_redirect_response=False,
        )

    def test_considered_retry_after_a_decline_is_allowed(self):
        first_order = self._order()
        self._existing_payment(first_order, PaymentStatus.REJECTED, age=timedelta(minutes=2))

        response = self.client.get(self._create_payment_url(self._order()))

        self.assertEqual(Payment.objects.count(), 2)
        new_payment = Payment.objects.exclude(order=first_order).get()
        self.assertRedirects(
            response,
            reverse("payment_details", kwargs={"payment_id": new_payment.id}),
            fetch_redirect_response=False,
        )

    def test_stale_in_flight_payment_does_not_block_forever(self):
        # An abandoned WAITING payment older than the join window must not
        # wall the user off from ever paying.
        self._existing_payment(self._order(), PaymentStatus.WAITING, age=timedelta(minutes=10))

        self.client.get(self._create_payment_url(self._order()))

        self.assertEqual(Payment.objects.count(), 2)

    def test_other_users_payments_do_not_interfere(self):
        stranger = baker.make("User")
        baker.make(
            Payment,
            order__user=stranger,
            variant="default",
            billing_email="bar@baz.cz",
            status=PaymentStatus.WAITING,
        )

        self.client.get(self._create_payment_url(self._order()))

        self.assertEqual(Payment.objects.filter(order__user=self.user).count(), 1)

    @override_settings(PLANS_PAYMENTS_JOIN_IN_FLIGHT_SECONDS=0)
    def test_join_guard_can_be_disabled(self):
        self._existing_payment(self._order(), PaymentStatus.WAITING, age=timedelta(seconds=30))

        self.client.get(self._create_payment_url(self._order()))

        self.assertEqual(Payment.objects.count(), 2)

    @override_settings(PLANS_PAYMENTS_DECLINE_COOLDOWN_SECONDS=0)
    def test_decline_cooldown_can_be_disabled(self):
        self._existing_payment(self._order(), PaymentStatus.REJECTED, age=timedelta(seconds=20))

        self.client.get(self._create_payment_url(self._order()))

        self.assertEqual(Payment.objects.count(), 2)


class PaymentDetailViewRedirectTests(TestCase):
    def test_payment_details_view_redirect_needed(self):
        """3-D Secure / CVV flow: get_form raising RedirectNeeded redirects."""
        user = baker.make("User")
        payment = baker.make(Payment, order__user=user, variant="default", billing_email="bar@baz.cz")
        self.client.force_login(user)
        with mock.patch.object(Payment, "get_form", side_effect=RedirectNeeded("https://3ds.example.com")):
            response = self.client.get(reverse("payment_details", kwargs={"payment_id": payment.id}))
        self.assertRedirects(response, "https://3ds.example.com", fetch_redirect_response=False)


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
