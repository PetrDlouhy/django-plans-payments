from django.contrib import admin

from . import models


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'variant',
        'status',
        'fraud_status',
        'currency',
        'total',
        'transaction_fee',
        'created',
        'modified',
    )
    readonly_fields = (
        'created',
        'modified',
    )


admin.site.register(models.Payment, PaymentAdmin)
