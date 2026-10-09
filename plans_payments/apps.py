# -*- coding: utf-8
from django.apps import AppConfig
from django.core.checks import register


class PlansPaymentsConfig(AppConfig):
    name = "plans_payments"

    def ready(self):
        from .checks import check_wallet_support

        register(check_wallet_support)
