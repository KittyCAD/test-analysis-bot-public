import os

from .default import *  # pylint: disable=wildcard-import,unused-wildcard-import

BASE_URL = "http://testserver.com"

###############################################################################
# Core

TEST = True
SECRET_KEY = "test"

###############################################################################
# Authentication

OIDC_RP_CLIENT_ID = "test-client-id"
OIDC_RP_CLIENT_SECRET = "test-client-secret"

POSTMARK_API_KEY = "test-postmark-key"

###############################################################################
# Databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_analysis_bot",  # automatically prefixed with "test_"
        "HOST": "127.0.0.1",
    }
}

if "CI" in os.environ:
    DATABASES["default"]["USER"] = "postgres"
    DATABASES["default"]["PASSWORD"] = "postgres"
