import logging
from enum import StrEnum

from django.contrib import messages
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth import logout as auth_logout
from django.core.exceptions import SuspiciousOperation
from django.http import HttpRequest, HttpResponse
from django.utils.module_loading import import_string

from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView
from requests.exceptions import RequestException

LOGGER = logging.getLogger(__name__)
OIDC_FAILURE_REQUEST_ATTRIBUTE = "_oidc_failure_reason"


class OIDCFailureReason(StrEnum):
    ACCESS_DENIED = "access_denied"
    DOMAIN_NOT_ALLOWED = "domain_not_allowed"
    EMAIL_INVALID = "email_invalid"
    EMAIL_UNVERIFIED = "email_unverified"
    IDENTITY_CONFLICT = "identity_conflict"
    INVALID_RESPONSE = "invalid_response"
    PROVIDER_ERROR = "provider_error"
    SESSION_EXPIRED = "session_expired"
    SUBJECT_MISSING = "subject_missing"
    UNKNOWN = "unknown"


# Authentik returns these when silent re-auth (prompt=none) can't continue.
_SESSION_REAUTH_ERRORS = frozenset(
    {"login_required", "interaction_required", "consent_required"}
)

FAILURE_MESSAGES = {
    OIDCFailureReason.ACCESS_DENIED: "Authentik denied access.",
    OIDCFailureReason.DOMAIN_NOT_ALLOWED: (
        "Your Authentik email domain is not configured."
    ),
    OIDCFailureReason.EMAIL_INVALID: (
        "Authentik did not provide a valid email address."
    ),
    OIDCFailureReason.EMAIL_UNVERIFIED: (
        "Authentik could not verify your email address."
    ),
    OIDCFailureReason.IDENTITY_CONFLICT: (
        "This Authentik identity conflicts with an existing account."
    ),
    OIDCFailureReason.INVALID_RESPONSE: (
        "Unable to verify Authentik's response. Try again or use email login."
    ),
    OIDCFailureReason.PROVIDER_ERROR: (
        "Unable to complete sign-in with Authentik. Try again or use email login."
    ),
    OIDCFailureReason.SESSION_EXPIRED: (
        "Your Authentik session expired. Sign in again to continue."
    ),
    OIDCFailureReason.SUBJECT_MISSING: (
        "Authentik did not provide a stable user identifier."
    ),
    OIDCFailureReason.UNKNOWN: (
        "Unable to sign you in with Authentik. Try again or use email login."
    ),
}


def set_oidc_failure(request: HttpRequest, reason: OIDCFailureReason) -> None:
    setattr(request, OIDC_FAILURE_REQUEST_ATTRIBUTE, reason)


def uses_oidc_backend(request: HttpRequest) -> bool:
    backend_path = request.session.get(BACKEND_SESSION_KEY)
    if not isinstance(backend_path, str):
        return False
    backend = import_string(backend_path)
    return issubclass(backend, OIDCAuthenticationBackend)


class AuthentikOIDCCallbackView(OIDCAuthenticationCallbackView):
    def get(self, request: HttpRequest) -> HttpResponse:
        if "code" not in request.GET and "error" not in request.GET:
            raise SuspiciousOperation("OIDC callback has no result")

        state = request.GET.get("state")
        known_states = request.session.get("oidc_states")
        if (
            not isinstance(known_states, dict)
            or not isinstance(state, str)
            or state not in known_states
        ):
            raise SuspiciousOperation(
                "OIDC callback state not found in session `oidc_states`!"
            )

        try:
            return super().get(request)
        except RequestException:
            LOGGER.exception("Authentik provider request failed during OIDC callback")
            if request.user.is_authenticated and uses_oidc_backend(request):
                set_oidc_failure(request, OIDCFailureReason.SESSION_EXPIRED)
            else:
                set_oidc_failure(request, OIDCFailureReason.PROVIDER_ERROR)
            return self.login_failure()
        except SuspiciousOperation:
            LOGGER.warning(
                "Authentik returned an invalid OIDC response",
                exc_info=True,
            )
            set_oidc_failure(request, OIDCFailureReason.INVALID_RESPONSE)
            return self.login_failure()

    def login_failure(self) -> HttpResponse:
        reason = self._failure_reason()
        LOGGER.warning("OIDC authentication failed: %s", reason.value)
        if self.request.user.is_authenticated and uses_oidc_backend(self.request):
            auth_logout(self.request)
        messages.error(self.request, FAILURE_MESSAGES[reason])
        return super().login_failure()

    def login_success(self) -> HttpResponse:
        if hasattr(self.request, OIDC_FAILURE_REQUEST_ATTRIBUTE):
            delattr(self.request, OIDC_FAILURE_REQUEST_ATTRIBUTE)
        return super().login_success()

    def _failure_reason(self) -> OIDCFailureReason:
        reason = getattr(self.request, OIDC_FAILURE_REQUEST_ATTRIBUTE, None)
        if isinstance(reason, OIDCFailureReason):
            delattr(self.request, OIDC_FAILURE_REQUEST_ATTRIBUTE)
            return reason
        error = self.request.GET.get("error")
        if error == "access_denied":
            return OIDCFailureReason.ACCESS_DENIED
        if error in _SESSION_REAUTH_ERRORS:
            return OIDCFailureReason.SESSION_EXPIRED
        if error:
            return OIDCFailureReason.PROVIDER_ERROR
        return OIDCFailureReason.UNKNOWN
