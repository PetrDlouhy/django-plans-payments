from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from payments import PaymentStatus
from plans.models import Order
from related_admin import RelatedFieldAdmin

from . import models


class FaultyPaymentsFilter(SimpleListFilter):
    title = 'faulty_payments'
    parameter_name = 'faulty_payments'

    def lookups(self, request, model_admin):
        return [
            ('unconfirmed_order', 'Confirmed payment unconfirmed order'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'unconfirmed_order':
            return queryset.filter(status=PaymentStatus.CONFIRMED).\
                exclude(order__status=Order.STATUS.COMPLETED)
        return queryset


@admin.register(models.Payment)
class PaymentAdmin(RelatedFieldAdmin):
    list_display = (
        'id',
        'transaction_id',
        'token',
        'order__user',
        'variant',
        'status',
        'fraud_status',
        'currency',
        'total',
        'customer_ip_address',
        'tax',
        'transaction_fee',
        'captured_amount',
        'created',
        'modified',
        'autorenewed_payment',
    )
    list_filter = (
        'status',
        'variant',
        'fraud_status',
        'currency',
        'autorenewed_payment',
        FaultyPaymentsFilter,
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
    autocomplete_fields = (
        'order',
    )
    readonly_fields = (
        'created',
        'modified',
    )
