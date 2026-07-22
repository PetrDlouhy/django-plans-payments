from django.dispatch import Signal

# Sent when a payment provider reports the stored recurring token as
# permanently dead and it gets marked unverified. Host apps can listen to
# prompt the user to update their payment method.
# Arguments: "payment", "recurring_user_plan"
renew_token_invalidated = Signal()
