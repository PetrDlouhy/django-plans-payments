from django.core.checks import Warning
from payments import get_payment_model


def check_wallet_support(app_configs, **kwargs):
    """Warn when the installed django-payments cannot charge a stored card.

    renew_accounts() charges renewals through Payment.autocomplete_with_wallet(),
    which django-payments releases do not have yet; without it every automatic
    renewal fails with an AttributeError on the day it is due.
    """
    if hasattr(get_payment_model(), "autocomplete_with_wallet"):
        return []
    return [
        Warning(
            "The installed django-payments has no Payment.autocomplete_with_wallet(), "
            "so automatic renewals (renew_accounts) fail.",
            hint="Install a django-payments version with the wallet interface "
            "(github.com/PetrDlouhy/django-payments), or don't arm task-triggered renewals.",
            id="plans_payments.W001",
        )
    ]
