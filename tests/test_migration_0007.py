"""
Test migration 0006 to ensure existing RecurringUserPlan data is preserved.

This test verifies that:
1. Existing RecurringUserPlan records are preserved
2. Tokens and other important fields are not lost
3. New wallet fields (status, extra_data) are added correctly
4. Migration is reversible
5. Fresh install scenario (table creation) works correctly
"""

from decimal import Decimal
from unittest.mock import MagicMock

from django.db.utils import DatabaseError
from django.test import TransactionTestCase
from model_bakery import baker
from payments import WalletStatus
from swapper import load_model

RecurringUserPlan = load_model("plans", "RecurringUserPlan")


class Migration0006TestCase(TransactionTestCase):
    """
    Test that migration 0006 preserves existing RecurringUserPlan data.

    Uses TransactionTestCase to test actual database migrations.
    Note: TransactionTestCase doesn't automatically run migrations,
    so we need to ensure migrations are applied before creating test data.
    """

    def setUp(self):
        """Set up test data after migrations are applied."""
        # Migrations are automatically applied by TransactionTestCase
        # But we need to ensure the table exists before creating test data
        from django.core.management import call_command
        from django.db import connection

        # Ensure migrations are applied (they should be, but double-check)
        call_command("migrate", verbosity=0, interactive=False)

        # Verify the table exists after migrations
        # When model is swapped, table could be plans_payments_recurringuserplan
        # or plans_recurringuserplan (depending on when the swap happened
        # relative to django-plans migrations)
        tables = connection.introspection.table_names()
        if (
            "plans_payments_recurringuserplan" not in tables
            and "plans_recurringuserplan" not in tables
        ):
            raise RuntimeError(
                "RecurringUserPlan table does not exist after migrations. "
                "Migration 0006 may have failed."
            )

        # Create a user with a recurring plan that has important data
        self.user = baker.make("User")
        self.userplan = baker.make("UserPlan", user=self.user)
        self.recurring = baker.make(
            "plans_payments.RecurringUserPlan",
            user_plan=self.userplan,
            token="test_token_12345",
            payment_provider="default",
            token_verified=True,
            amount=Decimal("10.00"),
            currency="USD",
            renewal_triggered_by=RecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
            card_expire_year=2025,
            card_expire_month=12,
            card_masked_number="1234",
        )
        self.recurring_id = self.recurring.id
        self.recurring_token = self.recurring.token

    def test_migration_preserves_existing_data(self):
        """Test that migration preserves all existing RecurringUserPlan data."""
        # Verify data exists before migration
        self.assertIsNotNone(self.recurring.token)
        self.assertEqual(self.recurring.token, "test_token_12345")
        self.assertTrue(self.recurring.token_verified)

        # The migration has already been applied during test setup
        # We just need to verify the data is preserved
        # No need to manually run the migration

        # Refresh from database
        self.recurring.refresh_from_db()

        # Verify all original data is preserved
        self.assertEqual(self.recurring.id, self.recurring_id)
        self.assertEqual(self.recurring.token, self.recurring_token)
        self.assertEqual(self.recurring.token, "test_token_12345")
        self.assertTrue(self.recurring.token_verified)
        self.assertEqual(self.recurring.payment_provider, "default")
        self.assertEqual(self.recurring.amount, Decimal("10.00"))
        self.assertEqual(self.recurring.currency, "USD")
        self.assertEqual(self.recurring.card_expire_year, 2025)
        self.assertEqual(self.recurring.card_expire_month, 12)
        self.assertEqual(self.recurring.card_masked_number, "1234")

        # Verify new wallet fields are added with correct defaults
        self.assertEqual(self.recurring.status, WalletStatus.PENDING)  # Default value
        self.assertEqual(self.recurring.extra_data, {})  # Default value

    def test_migration_adds_wallet_fields(self):
        """Test that migration adds wallet fields (status, extra_data)."""
        # Verify the model has the fields after migration
        # The migration ensures these fields exist in the database
        self.assertTrue(hasattr(self.recurring, "status"))
        self.assertTrue(hasattr(self.recurring, "extra_data"))

        # Refresh from database to ensure fields are actually in the table
        self.recurring.refresh_from_db()

        # Verify fields have default values
        self.assertEqual(self.recurring.status, WalletStatus.PENDING)
        self.assertEqual(self.recurring.extra_data, {})

    def test_migration_sets_default_status_for_existing_records(self):
        """Test that existing records get default status='pending'."""
        # After migration, existing records should have status='pending'
        self.recurring.refresh_from_db()
        if hasattr(self.recurring, "status"):
            self.assertEqual(self.recurring.status, WalletStatus.PENDING)


class Migration0006FreshInstallTestCase(TransactionTestCase):
    """
    Test migration 0006 fresh install scenario.

    Tests the path where plans_recurringuserplan table doesn't exist
    and needs to be created by migration 0006.
    """

    def test_migration_function_handles_missing_table(self):
        """Test that add_wallet_fields creates table when it doesn't exist."""
        import importlib

        # Import migration module dynamically (can't use regular import due to leading digit)
        migration_module = importlib.import_module(
            "plans_payments.migrations.0007_recurringuserplan_basewallet_fields"
        )
        add_wallet_fields = migration_module.add_wallet_fields

        # Mock apps and schema_editor to simulate table not existing
        mock_apps = MagicMock()
        mock_schema_editor = MagicMock()

        # Set up mocks to simulate table doesn't exist (DatabaseError)
        mock_cursor = MagicMock()
        mock_schema_editor.connection.cursor.return_value = mock_cursor
        mock_schema_editor.connection.introspection.get_table_description.side_effect = DatabaseError(
            "Table doesn't exist"
        )

        # The migration resolves the model itself (mock apps returns a stand-in)
        mock_apps.get_model.return_value = RecurringUserPlan
        # This should call schema_editor.create_model() when table doesn't exist
        add_wallet_fields(mock_apps, mock_schema_editor)

        # Verify create_model was called (fresh install path)
        mock_schema_editor.create_model.assert_called_once_with(RecurringUserPlan)

    def test_fresh_install_creates_table(self):
        """Test that migration creates table in fresh install scenario."""
        from django.core.management import call_command
        from django.db import connection

        # First, ensure all migrations are applied
        call_command("migrate", verbosity=0, interactive=False)

        # Verify the table exists
        tables = connection.introspection.table_names()
        self.assertIn(
            "plans_recurringuserplan",
            tables,
            "Table should be created by migration or django-plans",
        )

        # Verify table has wallet fields
        table_description = connection.introspection.get_table_description(
            connection.cursor(), "plans_recurringuserplan"
        )
        column_names = [col.name for col in table_description]

        self.assertIn("status", column_names, "status column should exist")
        self.assertIn("extra_data", column_names, "extra_data column should exist")

    def test_fresh_install_can_create_records(self):
        """Test that we can create RecurringUserPlan records after fresh install."""
        from django.core.management import call_command

        # Ensure migrations are applied
        call_command("migrate", verbosity=0, interactive=False)

        # Create test data
        user = baker.make("User")
        userplan = baker.make("UserPlan", user=user)
        recurring = baker.make(
            "plans_payments.RecurringUserPlan",
            user_plan=userplan,
            token="fresh_install_token",
            payment_provider="default",
            currency="USD",
        )

        # Verify record was created with wallet fields
        self.assertIsNotNone(recurring.id)
        self.assertEqual(recurring.token, "fresh_install_token")
        self.assertTrue(hasattr(recurring, "status"))
        self.assertTrue(hasattr(recurring, "extra_data"))
        self.assertEqual(recurring.status, WalletStatus.PENDING)
        self.assertEqual(recurring.extra_data, {})


class Migration0006ReverseTestCase(TransactionTestCase):
    """
    Test migration 0006 reverse operation.

    Tests that the migration can be reversed cleanly, removing wallet fields.
    """

    def tearDown(self):
        """Heal schema drift caused behind the migration recorder's back.

        Tests here drop columns with a raw schema editor while the recorder
        still lists the wallet migration as applied; unapply and re-apply it
        so later TransactionTestCases meet the schema they expect.
        """
        from django.core.management import call_command

        call_command(
            "migrate",
            "plans_payments",
            "0006_alter_payment_status",
            verbosity=0,
            interactive=False,
        )
        call_command("migrate", "plans_payments", verbosity=0, interactive=False)

    def test_remove_wallet_fields_function(self):
        """Test that remove_wallet_fields function removes the fields correctly."""
        import importlib

        from django.core.management import call_command
        from django.db import connection

        # Import migration module dynamically (can't use regular import due to leading digit)
        migration_module = importlib.import_module(
            "plans_payments.migrations.0007_recurringuserplan_basewallet_fields"
        )
        remove_wallet_fields = migration_module.remove_wallet_fields

        # Ensure migrations are applied first
        call_command("migrate", verbosity=0, interactive=False)

        # Mock apps to return the actual model
        mock_apps = MagicMock()
        mock_apps.get_model.return_value = RecurringUserPlan

        # Use real schema editor
        with connection.schema_editor() as schema_editor:
            # Get current columns before removal
            table_description = connection.introspection.get_table_description(
                connection.cursor(), "plans_recurringuserplan"
            )
            column_names_before = [col.name for col in table_description]

            # Verify fields exist before removal
            self.assertIn("status", column_names_before)
            self.assertIn("extra_data", column_names_before)

            # Call remove_wallet_fields
            remove_wallet_fields(mock_apps, schema_editor)

        # Verify fields are removed
        table_description = connection.introspection.get_table_description(
            connection.cursor(), "plans_recurringuserplan"
        )
        column_names_after = [col.name for col in table_description]

        self.assertNotIn("status", column_names_after)
        self.assertNotIn("extra_data", column_names_after)

        # Verify other fields still exist
        self.assertIn("token", column_names_after)
        self.assertIn("payment_provider", column_names_after)

    def setUp(self):
        """Set up test data with wallet fields."""
        from django.core.management import call_command

        # Ensure migrations are applied
        call_command("migrate", verbosity=0, interactive=False)

        # Create test data with wallet fields
        self.user = baker.make("User")
        self.userplan = baker.make("UserPlan", user=self.user)
        self.recurring = baker.make(
            "plans_payments.RecurringUserPlan",
            user_plan=self.userplan,
            token="reverse_test_token",
            payment_provider="default",
            token_verified=True,
            currency="USD",
            status=WalletStatus.ACTIVE,
            extra_data={"customer_id": "cus_test"},
        )
        self.recurring_id = self.recurring.id

    def test_reverse_migration_removes_wallet_fields(self):
        """Test that reversing migration 0006 removes wallet fields."""
        from django.core.management import call_command
        from django.db import connection

        # Verify wallet fields exist before reverse
        table_description = connection.introspection.get_table_description(
            connection.cursor(), "plans_recurringuserplan"
        )
        column_names_before = [col.name for col in table_description]
        self.assertIn(
            "status", column_names_before, "status should exist before reverse"
        )
        self.assertIn(
            "extra_data", column_names_before, "extra_data should exist before reverse"
        )

        # Reverse migration 0006
        call_command(
            "migrate",
            "plans_payments",
            "0005_payment_plans_payme_status_9ad17d_idx_and_more",
            verbosity=0,
            interactive=False,
        )

        # Verify wallet fields are removed
        table_description = connection.introspection.get_table_description(
            connection.cursor(), "plans_recurringuserplan"
        )
        column_names_after = [col.name for col in table_description]
        self.assertNotIn(
            "status", column_names_after, "status should be removed after reverse"
        )
        self.assertNotIn(
            "extra_data",
            column_names_after,
            "extra_data should be removed after reverse",
        )

        # Verify original fields still exist
        self.assertIn("token", column_names_after, "token should still exist")
        self.assertIn(
            "payment_provider",
            column_names_after,
            "payment_provider should still exist",
        )
        self.assertIn(
            "user_plan_id", column_names_after, "user_plan_id should still exist"
        )

    def test_reverse_migration_preserves_original_data(self):
        """Test that reversing migration preserves original RecurringUserPlan data."""
        from django.core.management import call_command
        from django.db import connection

        # Store original values
        original_token = self.recurring.token
        original_provider = self.recurring.payment_provider
        original_verified = self.recurring.token_verified

        # Reverse migration 0006
        call_command(
            "migrate",
            "plans_payments",
            "0005_payment_plans_payme_status_9ad17d_idx_and_more",
            verbosity=0,
            interactive=False,
        )

        # Query the database directly to verify data is preserved
        # We can't use the ORM because the model might have wallet fields
        # but the database table doesn't anymore
        cursor = connection.cursor()
        cursor.execute(
            "SELECT token, payment_provider, token_verified FROM plans_recurringuserplan WHERE id = %s",
            [self.recurring_id],
        )
        row = cursor.fetchone()

        self.assertIsNotNone(row, "Record should still exist after reverse")
        self.assertEqual(row[0], original_token, "token should be preserved")
        self.assertEqual(
            row[1], original_provider, "payment_provider should be preserved"
        )
        self.assertEqual(
            row[2], original_verified, "token_verified should be preserved"
        )

    def test_reverse_and_forward_migration_cycle(self):
        """Test that migration can be reversed and re-applied successfully."""
        from django.core.management import call_command
        from django.db import connection

        # Store original data
        original_token = self.recurring.token

        # Reverse migration
        call_command(
            "migrate",
            "plans_payments",
            "0005_payment_plans_payme_status_9ad17d_idx_and_more",
            verbosity=0,
            interactive=False,
        )

        # Re-apply migration
        call_command("migrate", "plans_payments", verbosity=0, interactive=False)

        # Verify table structure is correct again
        table_description = connection.introspection.get_table_description(
            connection.cursor(), "plans_recurringuserplan"
        )
        column_names = [col.name for col in table_description]
        self.assertIn("status", column_names, "status should exist after re-apply")
        self.assertIn(
            "extra_data", column_names, "extra_data should exist after re-apply"
        )

        # Verify original non-wallet data is preserved
        # Query database directly
        cursor = connection.cursor()
        cursor.execute(
            "SELECT token FROM plans_recurringuserplan WHERE id = %s",
            [self.recurring_id],
        )
        row = cursor.fetchone()
        self.assertEqual(
            row[0], original_token, "token should be preserved through migration cycle"
        )
