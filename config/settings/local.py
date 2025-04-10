from .default import *  # pylint: disable=wildcard-import,unused-wildcard-import

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
# Databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_analysis_bot_dev",
        "HOST": "127.0.0.1",
    }
}

if "DATABASE_URL" in os.environ:
    DATABASES["default"] = dj_database_url.config()
