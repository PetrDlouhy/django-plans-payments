# Generated manually for RecurringUserPlan(BaseWallet) implementation
#
# This migration adds BaseWallet fields (status, extra_data) to RecurringUserPlan.
#
# Migration strategy:
# - Use SeparateDatabaseAndState with STATIC field definitions
# - state_operations: Register model with all fields from AbstractRecurringUserPlan + BaseWallet
# - database_operations: Only add the new BaseWallet fields (status, extra_data)
# - Static fields avoid import-time circular dependencies
# - Works for both blank DB and existing DB

from django.conf import settings
from django.db import migrations, models
from django.db.utils import DatabaseError


def add_wallet_fields(apps, schema_editor):
    """Add BaseWallet fields (status, extra_data) if RecurringUserPlan is swapped to plans_payments."""
    swappable_model = getattr(settings, "PLANS_RECURRINGUSERPLAN_MODEL", None)
    if not swappable_model or not swappable_model.startswith("plans_payments."):
        return

    # Try to get model from migration state (after state_operations)
    # Note: With SeparateDatabaseAndState, state_operations run first and update the state,
    # but the `apps` parameter passed to RunPython is still the state BEFORE this migration.
    # So we need to get the model from the actual Django app registry instead.
    RecurringUserPlan = None

    # First try migration state (might work if state was updated)
    try:
        RecurringUserPlan = apps.get_model("plans_payments", "RecurringUserPlan")
    except LookupError:
        pass

    # If not in migration state, try to get from actual app
    if RecurringUserPlan is None:
        try:
            from plans_payments.models import RecurringUserPlan as ActualModel

            RecurringUserPlan = ActualModel
        except (ImportError, AttributeError):
            # Model not available - can't proceed
            RecurringUserPlan = None

    # Table name is always plans_recurringuserplan (from db_table in Meta)
    expected_db_table = "plans_recurringuserplan"

    # Check if table exists - could be under new or old name
    actual_db_table = None
    existing_column_names = []
    table_exists = False

    try:
        existing_columns = schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(), expected_db_table
        )
        existing_column_names = [col.name for col in existing_columns]
        actual_db_table = expected_db_table
        table_exists = True
    except DatabaseError:
        # Table doesn't exist under expected name - check old name
        old_table = "plans_recurringuserplan"
        try:
            existing_columns = (
                schema_editor.connection.introspection.get_table_description(
                    schema_editor.connection.cursor(), old_table
                )
            )
            existing_column_names = [col.name for col in existing_columns]
            actual_db_table = old_table
            table_exists = True
        except DatabaseError:
            # Table doesn't exist - this is a fresh install scenario
            # The CreateModel in state_operations will handle table creation
            # We just need to ensure wallet fields are included
            table_exists = False

    # If table doesn't exist, we need to create it
    # (CreateModel in state_operations only updates migration state, not database)
    # This happens in fresh installs where PLANS_RECURRINGUSERPLAN_MODEL='plans_payments.RecurringUserPlan'
    # from the start, so django-plans migrations skip creating the table.
    # The model should be available from migration state after state_operations run.
    # However, the `apps` parameter is the state BEFORE this migration, so we need to
    # get the model from the actual app or create it dynamically.
    if not table_exists:
        # Try to get the actual model from the app (avoids registration conflicts)
        try:
            from plans_payments.models import RecurringUserPlan as ActualModel

            RecurringUserPlan = ActualModel
        except (ImportError, AttributeError):
            # Model not available - can't create table without it
            # This shouldn't happen, but if it does, skip table creation
            # The table will need to be created by a subsequent migration
            return

        # Create the table with all fields from the actual model
        schema_editor.create_model(RecurringUserPlan)
        return

    # Table exists - add wallet fields if they don't exist
    if RecurringUserPlan is not None:
        # We have the model - use schema_editor.add_field() (database-agnostic)
        # Temporarily update db_table if it differs from expected
        original_db_table = RecurringUserPlan._meta.db_table
        if actual_db_table != expected_db_table:
            RecurringUserPlan._meta.db_table = actual_db_table

        try:
            # Add fields using Django's schema editor API
            # Django's add_field() with default= applies defaults to existing rows
            # for SQLite and PostgreSQL automatically
            if "status" not in existing_column_names:
                status_field = models.CharField(max_length=10, default="pending")
                status_field.set_attributes_from_name("status")
                status_field.model = RecurringUserPlan
                schema_editor.add_field(RecurringUserPlan, status_field)

            if "extra_data" not in existing_column_names:
                extra_data_field = models.JSONField(default=dict, blank=True)
                extra_data_field.set_attributes_from_name("extra_data")
                extra_data_field.model = RecurringUserPlan
                schema_editor.add_field(RecurringUserPlan, extra_data_field)
        finally:
            if actual_db_table != expected_db_table:
                RecurringUserPlan._meta.db_table = original_db_table
    else:
        # Model not available from migration state - try to get from actual app
        try:
            from plans_payments.models import RecurringUserPlan as ActualModel

            RecurringUserPlan = ActualModel
        except (ImportError, AttributeError):
            # Model not available - can't proceed
            return

        # Temporarily update db_table if it differs from expected
        original_db_table = RecurringUserPlan._meta.db_table
        if actual_db_table != expected_db_table:
            RecurringUserPlan._meta.db_table = actual_db_table

        try:
            # Add fields using Django's schema editor API
            # Django's add_field() with default= applies defaults to existing rows
            # for SQLite and PostgreSQL automatically
            if "status" not in existing_column_names:
                status_field = models.CharField(max_length=10, default="pending")
                status_field.set_attributes_from_name("status")
                status_field.model = RecurringUserPlan
                schema_editor.add_field(RecurringUserPlan, status_field)

            if "extra_data" not in existing_column_names:
                extra_data_field = models.JSONField(default=dict, blank=True)
                extra_data_field.set_attributes_from_name("extra_data")
                extra_data_field.model = RecurringUserPlan
                schema_editor.add_field(RecurringUserPlan, extra_data_field)
        finally:
            if actual_db_table != expected_db_table:
                RecurringUserPlan._meta.db_table = original_db_table


def remove_wallet_fields(apps, schema_editor):
    """Remove BaseWallet fields if RecurringUserPlan is swapped to plans_payments."""
    swappable_model = getattr(settings, "PLANS_RECURRINGUSERPLAN_MODEL", None)
    if not swappable_model or not swappable_model.startswith("plans_payments."):
        return

    try:
        RecurringUserPlan = apps.get_model("plans_payments", "RecurringUserPlan")
        db_table = RecurringUserPlan._meta.db_table
        existing_columns = schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(), db_table
        )
        existing_column_names = [col.name for col in existing_columns]
    except (LookupError, DatabaseError):
        return

    status_field = models.CharField(max_length=10)
    status_field.set_attributes_from_name("status")
    status_field.model = RecurringUserPlan

    extra_data_field = models.JSONField(default=dict, blank=True)
    extra_data_field.set_attributes_from_name("extra_data")
    extra_data_field.model = RecurringUserPlan

    if "extra_data" in existing_column_names:
        schema_editor.remove_field(RecurringUserPlan, extra_data_field)

    if "status" in existing_column_names:
        schema_editor.remove_field(RecurringUserPlan, status_field)


class Migration(migrations.Migration):
    dependencies = [
        ("plans_payments", "0005_payment_plans_payme_status_9ad17d_idx_and_more"),
        migrations.swappable_dependency(settings.PLANS_RECURRINGUSERPLAN_MODEL),
        # Explicit dependency on the migration that originally created the table
        # Without this, Django might try to run this migration before the table exists
        ("plans", "0005_recurring_payments"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_wallet_fields,
                    remove_wallet_fields,
                ),
            ],
            state_operations=[
                # Register RecurringUserPlan in plans_payments migration state
                # Uses STATIC field definitions to avoid import-time circular dependencies
                migrations.CreateModel(
                    name="RecurringUserPlan",
                    fields=[
                        # Primary key
                        (
                            "id",
                            models.AutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        # From BaseMixin (django-plans)
                        (
                            "created",
                            models.DateTimeField(
                                auto_now_add=True,
                                blank=True,
                                db_index=True,
                                null=True,
                                verbose_name="created",
                            ),
                        ),
                        ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                        # From AbstractRecurringUserPlan
                        (
                            "user_plan",
                            models.OneToOneField(
                                on_delete=models.deletion.CASCADE,
                                related_name="recurring",
                                to="plans.userplan",
                            ),
                        ),
                        (
                            "token",
                            models.CharField(
                                blank=True,
                                default=None,
                                help_text=(
                                    "Token, that will be used for payment renewal. "
                                    "Depends on used payment provider"
                                ),
                                max_length=255,
                                null=True,
                                verbose_name="recurring token",
                            ),
                        ),
                        (
                            "payment_provider",
                            models.CharField(
                                blank=True,
                                default=None,
                                help_text="Provider, that will be used for payment renewal",
                                max_length=255,
                                null=True,
                                verbose_name="payment provider",
                            ),
                        ),
                        (
                            "pricing",
                            models.ForeignKey(
                                blank=True,
                                default=None,
                                help_text="Recurring pricing",
                                null=True,
                                on_delete=models.deletion.CASCADE,
                                to="plans.pricing",
                            ),
                        ),
                        (
                            "amount",
                            models.DecimalField(
                                blank=True,
                                db_index=True,
                                decimal_places=2,
                                max_digits=7,
                                null=True,
                                verbose_name="amount",
                            ),
                        ),
                        (
                            "tax",
                            models.DecimalField(
                                blank=True,
                                db_index=True,
                                decimal_places=2,
                                max_digits=4,
                                null=True,
                                verbose_name="tax",
                            ),
                        ),
                        (
                            "currency",
                            models.CharField(max_length=3, verbose_name="currency"),
                        ),
                        (
                            "renewal_triggered_by",
                            models.IntegerField(
                                choices=[(1, "other"), (2, "user"), (3, "task")],
                                db_index=True,
                                default=2,
                                help_text=(
                                    "The source of the associated plan's renewal "
                                    "(USER = user-initiated renewal, "
                                    "TASK = autorenew_account-task-initiated renewal, "
                                    "OTHER = renewal is triggered using another mechanism)."
                                ),
                                verbose_name="renewal triggered by",
                            ),
                        ),
                        (
                            "_has_automatic_renewal_backup_deprecated",
                            models.BooleanField(
                                db_column="has_automatic_renewal",
                                default=False,
                                help_text=(
                                    "Automatic renewal is enabled for associated plan. "
                                    "If False, the plan renewal can be still initiated by user."
                                ),
                                verbose_name="has automatic plan renewal",
                            ),
                        ),
                        (
                            "token_verified",
                            models.BooleanField(
                                default=False,
                                help_text=(
                                    "The recurring token has been verified "
                                    "by at least one payment to be working."
                                ),
                                verbose_name="token has been verified by payment",
                            ),
                        ),
                        (
                            "card_expire_year",
                            models.IntegerField(blank=True, null=True),
                        ),
                        (
                            "card_expire_month",
                            models.IntegerField(blank=True, null=True),
                        ),
                        (
                            "card_masked_number",
                            models.CharField(blank=True, max_length=255, null=True),
                        ),
                        (
                            "last_renewal_attempt",
                            models.DateTimeField(
                                blank=True,
                                null=True,
                                verbose_name="last renewal attempt",
                            ),
                        ),
                        # From BaseWallet (django-payments)
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("pending", "Pending"),
                                    ("active", "Active"),
                                    ("erased", "Erased"),
                                ],
                                default="pending",
                                max_length=10,
                            ),
                        ),
                        (
                            "extra_data",
                            models.JSONField(
                                blank=False,
                                default=dict,
                                help_text=(
                                    "Provider-specific data "
                                    "(e.g., card details, expiry dates, customer IDs)"
                                ),
                                null=False,
                                verbose_name="extra data",
                            ),
                        ),
                    ],
                    options={
                        "swappable": "PLANS_RECURRINGUSERPLAN_MODEL",
                        "db_table": "plans_recurringuserplan",
                    },
                ),
            ],
        ),
    ]
