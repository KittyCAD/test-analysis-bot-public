import os

import dj_database_url

from .default import *  # pylint: disable=wildcard-import,unused-wildcard-import

###############################################################################
# Core

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [
    "0.0.0.0",
    "localhost",
    ".herokuapp.com",  # TODO: Remove this line and add your custom domain
]

CSRF_TRUSTED_ORIGINS = [
    "https://*herokuapp.com",  # TODO: Remove this line and add your custom domain
]

###############################################################################
# Authentication

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

###############################################################################
# Static files

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
