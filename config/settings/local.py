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

INSTALLED_APPS += [
    "django_browser_reload",
]

MIDDLEWARE += [
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

if not OIDC_RP_CLIENT_ID:
    MIDDLEWARE.remove("tab.core.middleware.AuthentikSessionRefresh")

###############################################################################
# Logging

LOGGING["handlers"]["console"]["formatter"] = "standard"
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

if "REDIS_URL" in os.environ:
    CACHES["default"]["BACKEND"] = "django.core.cache.backends.redis.RedisCache"
    CACHES["default"]["LOCATION"] = os.environ["REDIS_URL"]

###############################################################################
# Debug Toolbar

DEBUG_TOOLBAR_CONFIG["SHOW_TOOLBAR_CALLBACK"] = lambda request: True  # type: ignore[assignment]
