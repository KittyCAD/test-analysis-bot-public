import logging
import sys
import traceback

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


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
        logger.critical(
            f"Unhandled exception for {request.method} {request.path}\n{tb_text}",
            exc_info=False,  # Don't include exc_info since we're formatting it ourselves
        )

        return None
