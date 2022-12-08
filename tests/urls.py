# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("", include("plans_payments.urls")),
    path("login/", auth_views.LoginView.as_view(), name="auth_login"),
    path("", include("plans.urls")),
]
