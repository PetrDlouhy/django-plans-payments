# Generated by Django 3.0.10 on 2020-10-06 06:55

from decimal import Decimal

import phonenumber_field.modelfields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plans_payments", "0002_payment_transaction_fee"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="autorenewed_payment",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="payment",
            name="transaction_fee",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.0"), max_digits=9
            ),
        ),
    ]
