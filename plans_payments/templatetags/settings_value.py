from django import template
from django.conf import settings
from django.urls import reverse

from payments.core import provider_factory

register = template.Library()

# settings value
@register.inclusion_tag("plans_payments/payment_buttons.html")
def settings_value(object_variable):
    variants = getattr(settings, 'PAYMENT_VARIANTS', [])
    #for variant in variants:
    #    variant.url = reverse("create_payment", kwargs={'payment_variant': 'default', 'order_id': object_id})

    print(variants)
    return {
        'variants': variants,
        'object': object_variable,
    }
