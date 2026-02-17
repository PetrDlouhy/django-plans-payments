# -*- coding: utf-8
from tests.settings import *  # noqa: F403,F401

# Add test_app to INSTALLED_APPS (simulates BlenderKit with FK to RecurringUserPlan)
INSTALLED_APPS = list(INSTALLED_APPS) + ["tests.test_app"]  # noqa: F405

# Set swappable model to plans_payments (like BlenderKit does)
PLANS_RECURRINGUSERPLAN_MODEL = "plans_payments.RecurringUserPlan"
