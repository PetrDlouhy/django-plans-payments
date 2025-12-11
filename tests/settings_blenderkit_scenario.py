# -*- coding: utf-8
from tests.settings import *

# test_app is already in INSTALLED_APPS from base settings
# Set swappable model to plans_payments (like BlenderKit does)
PLANS_RECURRINGUSERPLAN_MODEL = "plans_payments.RecurringUserPlan"

