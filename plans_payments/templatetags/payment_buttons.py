from django import template
from django.conf import settings
from django.urls import reverse

from payments.core import provider_factory

register = template.Library()

# settings value
@register.inclusion_tag("plans_payments/payment_buttons.html")
def payment_buttons(object_variable):
    variants = getattr(settings, 'PAYMENT_VARIANTS', [])
    return {
        'variants': variants,
        'object': object_variable,
    }
