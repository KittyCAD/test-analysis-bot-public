import os

from .default import *  # pylint: disable=wildcard-import,unused-wildcard-import

BASE_URL = "http://localhost:8000"

###############################################################################
# Core

DEBUG = True
SECRET_KEY = "local"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".ngrok.app",
]

INTERNAL_IPS = [
    "127.0.0.1",
]

INSTALLED_APPS += [
    "django_browser_reload",
    "debug_toolbar",
]

MIDDLEWARE += [
    "django_browser_reload.middleware.BrowserReloadMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

###############################################################################
# Logging

LOGGING["root"]["level"] = "DEBUG"

###############################################################################
# Databases

if "DATABASE_URL" not in os.environ:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "test_analysis_bot_dev",
            "HOST": "127.0.0.1",
        }
    }

###############################################################################
# Caches

CACHES["default"]["TIMEOUT"] = 30

if "REDIS_URL" in os.environ:
    CACHES["default"]["BACKEND"] = "django.core.cache.backends.redis.RedisCache"
    CACHES["default"]["LOCATION"] = os.environ["REDIS_URL"]
