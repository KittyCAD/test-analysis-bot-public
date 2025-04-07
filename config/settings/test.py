from .default import *  # pylint: disable=wildcard-import,unused-wildcard-import

###############################################################################
# Core

TEST = True
DEBUG = True
SECRET_KEY = "test"

###############################################################################
# Databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_analysis_bot",  # automatically prefixed with "test_"
        "HOST": "127.0.0.1",
    }
}

###############################################################################
# Caches

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / ".cache" / "django",
    }
}
