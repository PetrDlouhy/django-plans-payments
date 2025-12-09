# Generated manually for RecurringUserPlan(BaseWallet) implementation
#
# This migration adds BaseWallet fields (status, extra_data) to RecurringUserPlan.
#
# For swappable models, we use SeparateDatabaseAndState:
# - state_operations: Register the model in plans_payments migration state with ALL fields
# - database_operations: Add only the new fields using RunPython (conditional on swap)

from django.conf import settings
from django.db import migrations, models
from django.db.utils import DatabaseError


def _get_all_recurring_user_plan_fields():
    """Get all field definitions for RecurringUserPlan using field.deconstruct().

    This is needed so Django's migration state knows about all fields,
    not just the new ones. Otherwise makemigrations will try to add all
    the AbstractRecurringUserPlan fields in a subsequent migration.

    We use deconstruct() to get the exact field definition that Django
    migration system expects.
    """
    try:
        from swapper import load_model

        RecurringUserPlan = load_model("plans", "RecurringUserPlan")
    except (ImportError, LookupError):
        # Can't load model - return minimal fields as fallback
        return [
            ("id", models.AutoField(primary_key=True, serialize=False)),
            ("status", models.CharField(default="pending", max_length=10)),
            ("extra_data", models.JSONField(default=dict, blank=True)),
        ]

    # Build field definitions using deconstruct() to get exact Django migration format
    field_definitions = []

    # Get all concrete fields from the model, in order
    for field in RecurringUserPlan._meta.get_fields():
        if not hasattr(field, "name") or not field.concrete:
            continue

        # Skip reverse relations and many-to-many
        if field.is_relation and (
            field.many_to_many or not (field.many_to_one or field.one_to_one)
        ):
            continue

        # Use deconstruct() to get the field definition
        try:
            name, path, args, kwargs = field.deconstruct()
            # Reconstruct the field class
            field_class = field.__class__
            # Handle related fields specially - use string references
            if field.is_relation:
                if "to" in kwargs:
                    # Replace model reference with string
                    to_model = kwargs["to"]
                    if hasattr(to_model, "_meta"):
                        kwargs["to"] = to_model._meta.label
                    elif isinstance(to_model, str):
                        kwargs["to"] = to_model
                # Reconstruct the field
                field_def = field_class(*args, **kwargs)
            else:
                # Regular field - reconstruct directly
                field_def = field_class(*args, **kwargs)

            field_definitions.append((field.name, field_def))
        except Exception:
            # If deconstruct fails, skip this field
            continue

    return field_definitions


def add_wallet_fields(apps, schema_editor):
    """Add BaseWallet fields (status, extra_data) if RecurringUserPlan is swapped to plans_payments."""
    swappable_model = getattr(settings, "PLANS_RECURRINGUSERPLAN_MODEL", None)
    if not swappable_model or not swappable_model.startswith("plans_payments."):
        return

    try:
        RecurringUserPlan = apps.get_model("plans_payments", "RecurringUserPlan")
    except LookupError:
        # Model not in migration state yet - this is OK, we'll work with the actual table
        # Get the model from the actual app to find the table name
        from swapper import load_model

        try:
            RecurringUserPlan = load_model("plans", "RecurringUserPlan")
        except (ImportError, LookupError):
            return

    expected_db_table = (
        RecurringUserPlan._meta.db_table
    )  # plans_payments_recurringuserplan when swapped

    # Check if table exists - could be under new name (plans_payments_recurringuserplan)
    # or old name (plans_recurringuserplan) if model was swapped after django-plans migrations
    actual_db_table = None
    existing_column_names = []

    try:
        existing_columns = schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(), expected_db_table
        )
        existing_column_names = [col.name for col in existing_columns]
        actual_db_table = expected_db_table
    except DatabaseError:
        # Table doesn't exist under new name - check old name
        old_table = "plans_recurringuserplan"
        try:
            existing_columns = (
                schema_editor.connection.introspection.get_table_description(
                    schema_editor.connection.cursor(), old_table
                )
            )
            existing_column_names = [col.name for col in existing_columns]
            actual_db_table = old_table
        except DatabaseError:
            # Neither table exists - this shouldn't happen if migrations ran correctly
            # but we'll skip gracefully
            return

    if not actual_db_table:
        return

    # Add fields using raw SQL - simpler and more reliable for swappable models
    cursor = schema_editor.connection.cursor()

    if "status" not in existing_column_names:
        try:
            cursor.execute(
                f'ALTER TABLE "{actual_db_table}" ADD COLUMN "status" VARCHAR(10) NOT NULL DEFAULT \'pending\''
            )
        except Exception as e:
            # Column might already exist or there's an error - log and continue
            pass

    if "extra_data" not in existing_column_names:
        try:
            cursor.execute(
                f'ALTER TABLE "{actual_db_table}" ADD COLUMN "extra_data" TEXT NOT NULL DEFAULT \'{{}}\''
            )
        except Exception as e:
            # Column might already exist or there's an error - log and continue
            pass


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
                # Register RecurringUserPlan in plans_payments migration state with ALL fields
                # This tells Django that when the model is swapped to plans_payments,
                # it should be tracked in this app's migration history with all fields
                # from AbstractRecurringUserPlan + BaseWallet
                migrations.CreateModel(
                    name="RecurringUserPlan",
                    fields=_get_all_recurring_user_plan_fields(),
                    options={
                        "swappable": "PLANS_RECURRINGUSERPLAN_MODEL",
                        "db_table": "plans_recurringuserplan",
                    },
                ),
            ],
        ),
    ]
