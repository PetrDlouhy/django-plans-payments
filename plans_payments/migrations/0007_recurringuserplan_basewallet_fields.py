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

TABLE = "plans_recurringuserplan"


def _swapped_to_plans_payments():
    swappable_model = getattr(settings, "PLANS_RECURRINGUSERPLAN_MODEL", None)
    return bool(swappable_model) and swappable_model.startswith("plans_payments.")


def _get_recurring_model(apps):
    """Return the concrete swapped-in RecurringUserPlan model.

    The `apps` registry passed to RunPython reflects the migration state
    BEFORE this migration (its CreateModel lives in state_operations of the
    same migration), so fall back to the real app registry.
    """
    try:
        return apps.get_model("plans_payments", "RecurringUserPlan")
    except LookupError:
        from plans_payments.models import RecurringUserPlan

        return RecurringUserPlan


def _existing_columns(schema_editor, table):
    """Return (column names, table exists)."""
    try:
        description = schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(), table
        )
    except DatabaseError:
        return [], False
    return [column.name for column in description], True


WALLET_FIELD_NAMES = ("status", "extra_data")


def add_wallet_fields(apps, schema_editor):
    """Add BaseWallet columns when RecurringUserPlan is swapped to plans_payments."""
    if not _swapped_to_plans_payments():
        return
    model = _get_recurring_model(apps)
    column_names, table_exists = _existing_columns(schema_editor, TABLE)
    if not table_exists:
        # Fresh install with the swap active from the start: django-plans
        # skips creating the table for a swapped-out model, so create it here
        # with all fields (CreateModel in state_operations is state-only).
        schema_editor.create_model(model)
        return
    # Plain ADD COLUMN, deliberately not schema_editor.add_field(): SQLite
    # implements add_field() by rebuilding the table from the full model,
    # which references the OTHER wallet column while it is still missing
    # (SQLite then even reads the unknown quoted identifier as a string
    # literal, corrupting the copy). ADD COLUMN with a constant default is
    # supported by all backends and backfills existing rows.
    quote = schema_editor.quote_name
    json_type = "jsonb" if schema_editor.connection.vendor == "postgresql" else "text"
    column_sql = {
        "status": "varchar(10) NOT NULL DEFAULT 'pending'",
        "extra_data": f"{json_type} NOT NULL DEFAULT '{{}}'",
    }
    for name in WALLET_FIELD_NAMES:
        if name not in column_names:
            schema_editor.execute(
                f"ALTER TABLE {quote(TABLE)} ADD COLUMN "
                f"{quote(name)} {column_sql[name]}"
            )


def remove_wallet_fields(apps, schema_editor):
    """Drop the BaseWallet columns again (reverse of add_wallet_fields)."""
    if not _swapped_to_plans_payments():
        return
    model = _get_recurring_model(apps)
    column_names, table_exists = _existing_columns(schema_editor, TABLE)
    if not table_exists:
        return
    for name in reversed(WALLET_FIELD_NAMES):
        if name in column_names:
            schema_editor.remove_field(model, model._meta.get_field(name))


class Migration(migrations.Migration):
    dependencies = [
        ("plans_payments", "0006_alter_payment_status"),
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
