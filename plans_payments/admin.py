from django.contrib import admin

from related_admin import RelatedFieldAdmin

from . import models


class PaymentAdmin(RelatedFieldAdmin):
    list_display = (
        'id',
        'transaction_id',
        'order__user',
        'variant',
        'status',
        'fraud_status',
        'currency',
        'total',
        'customer_ip_address',
        'transaction_fee',
        'captured_amount',
        'created',
        'modified',
    )
    list_filter = (
        'status',
        'variant',
        'fraud_status',
        'currency',
    )
    search_fields = (
        'order__user__first_name',
        'order__user__last_name',
        'order__user__email',
        'transaction_id',
        'extra_data',
        'token',
    )
    list_select_related = (
        'order__user',
    )
    readonly_fields = (
        'created',
        'modified',
    )


admin.site.register(models.Payment, PaymentAdmin)
