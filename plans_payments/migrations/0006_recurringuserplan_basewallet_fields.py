# Generated manually for RecurringUserPlan(BaseWallet) implementation

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plans_payments", "0005_payment_plans_payme_status_9ad17d_idx_and_more"),
        ("plans", "__latest__"),  # RecurringUserPlan is from django-plans
    ]

    operations = [
        migrations.AddField(
            model_name="recurringuserplan",
            name="status",
            field=models.CharField(
                max_length=10,
                choices=[
                    ("pending", "Pending"),
                    ("active", "Active"),
                    ("erased", "Erased"),
                ],
                default="pending",
                help_text="Wallet status for recurring payments",
            ),
        ),
        migrations.AddField(
            model_name="recurringuserplan",
            name="extra_data",
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text="Provider-specific data (e.g., customer IDs)",
            ),
        ),
    ]

