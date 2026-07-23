"""
Test to replicate BlenderKit migration error.

This test simulates the scenario where another app (test_app) has a ForeignKey
to the swappable RecurringUserPlan model. When migrations run, Django needs to
resolve the model, but if migration 0006 doesn't declare swappable_dependency,
the model won't exist in the migration state yet, causing:

ValueError: Related model 'plans_payments.recurringuserplan' cannot be resolved

To manually replicate the error:
1. Run: DJANGO_SETTINGS_MODULE=tests.settings_blenderkit_scenario python manage.py test tests.test_blenderkit_scenario
2. Or manually: python manage.py migrate plans_payments 0005 && python manage.py migrate test_app

This test only runs when test_app is in INSTALLED_APPS (i.e., with settings_blenderkit_scenario.py).
"""

import unittest

from django.apps import apps
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings


@unittest.skipUnless(
    apps.is_installed("tests.test_app"),
    "test_app must be in INSTALLED_APPS (use settings_blenderkit_scenario.py)",
)
@override_settings(PLANS_RECURRINGUSERPLAN_MODEL="plans_payments.RecurringUserPlan")
class BlenderKitScenarioTestCase(TransactionTestCase):
    """
    Replicates BlenderKit error: another app with FK to RecurringUserPlan
    causes "Related model 'plans_payments.recurringuserplan' cannot be resolved"
    """

    def test_migration_with_external_fk_to_recurring_user_plan(self):
        """
        Test that swappable_dependency in migration 0006 fixes the BlenderKit error.

        This test verifies that when another app (test_app) has a ForeignKey to the
        swappable RecurringUserPlan, migrations run correctly because migration 0006
        declares swappable_dependency, which ensures 0006 runs before test_app's migration.

        Without swappable_dependency, test_app's migration would fail with:
        ValueError: Related model 'plans_payments.recurringuserplan' cannot be resolved

        With swappable_dependency (current implementation), migrations should work correctly.
        """
        # Run all migrations - this should work correctly with swappable_dependency
        call_command("migrate", verbosity=0, interactive=False)

        # Verify test_app.Order model exists and can be imported
        from tests.test_app.models import Order

        # Verify the ForeignKey to RecurringUserPlan works
        self.assertIsNotNone(Order._meta.get_field("recurring_plan"))
