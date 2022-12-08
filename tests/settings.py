# -*- coding: utf-8
from typing import Dict, Tuple

DEBUG = True
USE_TZ = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "-#5o&sf4iu8&-@na$ad*(t)0gl6_gnw-7_=mk5!zcck)p0w&30"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "tests.urls"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.messages",
    "plans",
    "payments",
    "plans_payments",
    "tests",
]

SITE_ID = 1
PAYMENT_MODEL = "plans_payments.Payment"

PAYMENT_VARIANTS: Dict[str, Tuple[str, Dict]] = {
    "default": ("payments.dummy.DummyProvider", {}),
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": True,
            "context_processors": [
                "django.template.context_processors.debug",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
