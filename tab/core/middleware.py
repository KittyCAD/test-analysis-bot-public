import sys
import traceback

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin

import log


class ExceptionLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to catch and log exceptions with single-line formatted stack traces.

    This ensures that when exceptions occur in the Django application, they are logged
    in a format that works well with log aggregation systems like Axiom by keeping
    the entire stack trace on a single log line.
    """

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> HttpResponse | None:
        # Get the full exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()

        # Format the traceback as a string
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = "".join(tb_lines)

        # Log the exception (the custom formatter will escape newlines)
        log.critical(
            f"Unhandled exception for {request.method} {request.path}\n{tb_text}",
            exc_info=False,  # Don't include exc_info since we're formatting it ourselves
        )

        return None


class DomainRedirectMiddleware(MiddlewareMixin):
    """
    Middleware to redirect from the legacy domain.
    """

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        if not settings.ALLOWED_HOSTS:
            return None

        legacy_domain = settings.ALLOWED_HOSTS[-1]
        if "test-analysis-bot" not in legacy_domain:
            return None

        request_host = request.get_host().split(":")[0]
        if request_host == legacy_domain:
            path = request.get_full_path()
            redirect_url = f"{settings.BASE_URL}{path}"
            log.warning(f"Redirecting from {request_host}{path} to {redirect_url}")
            return HttpResponsePermanentRedirect(redirect_url)

        return None
