import os

from .default import *  # pylint: disable=wildcard-import,unused-wildcard-import

BASE_URL = "https://test-analysis-bot.corp.zoo.dev"

###############################################################################
# Core

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [
    "0.0.0.0",
    "localhost",
    BASE_URL.removeprefix("https://"),
    "test-analysis-bot.hawk-dinosaur.ts.net",
]

CSRF_TRUSTED_ORIGINS = [
    BASE_URL,
    "https://test-analysis-bot.hawk-dinosaur.ts.net",
]

###############################################################################
# Caches

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
    }
}

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
