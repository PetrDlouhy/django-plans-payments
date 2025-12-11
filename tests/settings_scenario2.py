# Test settings for Scenario 2: Brand new project
# This simulates a user starting fresh with plans_payments.RecurringUserPlan

from tests.settings import *  # noqa: F403, F401

# Use plans_payments.RecurringUserPlan from the start
PLANS_RECURRINGUSERPLAN_MODEL = "plans_payments.RecurringUserPlan"
