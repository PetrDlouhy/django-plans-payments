from django.contrib import admin

from related_admin import RelatedFieldAdmin

from . import models


class PaymentAdmin(RelatedFieldAdmin):
    list_display = (
        'id',
        'order__user',
        'variant',
        'status',
        'fraud_status',
        'currency',
        'total',
        'transaction_fee',
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
    )
    list_select_related = (
        'order__user',
    )
    readonly_fields = (
        'created',
        'modified',
    )


admin.site.register(models.Payment, PaymentAdmin)
