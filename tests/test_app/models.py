from django.db import models
from swapper import get_model_name


class Order(models.Model):
    """Simulates a BlenderKit model with FK to RecurringUserPlan"""

    recurring_plan = models.ForeignKey(
        get_model_name("plans", "RecurringUserPlan"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
