import os
from pathlib import Path

from django.contrib import messages

import dj_database_url

BASE_DIR = Path(__file__).resolve().parents[2]


###############################################################################
# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # 3rd-party
    "corsheaders",
    "crispy_bootstrap5",
    "crispy_forms",
    "django_extensions",
    "django_tables2",
    # First-party
    "tab.api",
    "tab.core",
    "tab.projects",
    "tab.metrics",
    "tab.releases",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "tab.core.middleware.ExceptionLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

###############################################################################
# Logging

LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(levelname)s: %(message)s",
        },
        "json": {
            "()": "tab.core.logging.JSONFormatter",
        },
    },
    "filters": {
        "empty_log_filter": {
            "()": "tab.core.logging.EmptyLogFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["empty_log_filter"],
        },
    },
    "loggers": {
        "django.request": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

###############################################################################
# Databases

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASES = {}
DATABASES["default"] = dj_database_url.config()

###############################################################################
# Caches

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / ".cache" / "django",
    }
}

###############################################################################
# Internationalization

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

###############################################################################
# Static files

STATIC_ROOT = BASE_DIR / "staticfiles"

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

###############################################################################
# Crispy Forms

CRISPY_TEMPLATE_PACK = "bootstrap5"

MESSAGE_TAGS = {
    messages.DEBUG: "alert-secondary",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}

###############################################################################
# Email

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_HOST_USER = "apikey"
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
EMAIL_PORT = 587
EMAIL_USE_TLS = True
