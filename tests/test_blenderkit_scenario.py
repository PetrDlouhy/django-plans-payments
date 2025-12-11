"""
Test to replicate BlenderKit migration error.

This test simulates the scenario where another app (test_app) has a ForeignKey
to the swappable RecurringUserPlan model. When migrations run, Django needs to
resolve the model, but if migration 0006 doesn't declare swappable_dependency,
the model won't exist in the migration state yet, causing:

ValueError: Related model 'plans_payments.recurringuserplan' cannot be resolved

To manually replicate the error:
1. Run: python manage.py migrate plans_payments 0005
2. Run: python manage.py migrate test_app
3. This will fail with the error above

This test verifies that the error occurs when test_app migration runs before 0006.
"""

from django.core.management import call_command
from django.test import TransactionTestCase, override_settings


@override_settings(PLANS_RECURRINGUSERPLAN_MODEL="plans_payments.RecurringUserPlan")
class BlenderKitScenarioTestCase(TransactionTestCase):
    """
    Replicates BlenderKit error: another app with FK to RecurringUserPlan
    causes "Related model 'plans_payments.recurringuserplan' cannot be resolved"
    """

    def test_migration_with_external_fk_to_recurring_user_plan(self):
        """
        This REPLICATES the BlenderKit error.

        The error occurs when:
        1. test_app has a migration creating Order with FK to RecurringUserPlan
        2. Swappable setting resolves this to 'plans_payments.RecurringUserPlan'
        3. Migration 0006 creates the model in migration state, but if test_app
           migration runs before 0006, Django can't resolve the model
        4. This happens when migrations are run in a specific order or when
           test_app migration doesn't have swappable_dependency declared

        To replicate: Run migrations up to 0005, then try to run test_app migration.
        This should fail with ValueError: Related model 'plans_payments.recurringuserplan' cannot be resolved
        """
        # Step 1: Run migrations up to 0005 (before 0006 creates RecurringUserPlan)
        call_command(
            "migrate",
            "plans_payments",
            "0005_payment_plans_payme_status_9ad17d_idx_and_more",
            verbosity=0,
            interactive=False,
        )

        # Step 2: Try to run test_app migration before 0006
        # This should fail with the BlenderKit error
        # The error can manifest in two ways:
        # 1. "Related model 'plans_payments.recurringuserplan' cannot be resolved" (during CreateModel)
        # 2. "app 'plans_payments' doesn't provide model 'recurringuserplan'" (during state construction)
        # Both indicate the same root cause: model doesn't exist in migration state
        try:
            call_command("migrate", "test_app", verbosity=0, interactive=False)
            self.fail("Expected ValueError when migrating test_app before 0006")
        except ValueError as e:
            # Verify we got a related error (either form indicates the bug is replicated)
            error_msg = str(e)
            has_recurringuserplan = "recurringuserplan" in error_msg.lower()
            has_resolution_error = "cannot be resolved" in error_msg or "doesn't provide model" in error_msg

            self.assertTrue(
                has_recurringuserplan and has_resolution_error,
                f"Expected error about recurringuserplan resolution, got: {error_msg}",
            )
