from unittest.mock import Mock

from django.http import HttpRequest

import pytest

from tab.core.middleware import ExceptionLoggingMiddleware


def describe_exception_logging_middleware():
    @pytest.fixture
    def middleware():
        return ExceptionLoggingMiddleware(get_response=Mock())

    @pytest.fixture
    def http_request():
        req = HttpRequest()
        req.method = "GET"
        req.path = "/test-path/"
        return req

    def it_logs_exceptions(expect, mocker, middleware, http_request):
        mock_logger = mocker.patch("tab.core.middleware.logger")
        exception = ValueError("Test error")

        try:
            raise exception
        except ValueError:
            result = middleware.process_exception(http_request, exception)

        expect(mock_logger.critical.called).is_(True)

        call_args = mock_logger.critical.call_args
        log_message = call_args[0][0]

        expect(log_message).contains("GET")
        expect(log_message).contains("/test-path/")
        expect(log_message).contains("ValueError")
        expect(log_message).contains("Test error")
        expect(result).is_(None)

    def it_includes_stack_trace_in_log(expect, mocker, middleware, http_request):
        mock_logger = mocker.patch("tab.core.middleware.logger")
        exception = RuntimeError("Runtime error")

        try:
            raise exception
        except RuntimeError:
            middleware.process_exception(http_request, exception)

        call_args = mock_logger.critical.call_args
        log_message = call_args[0][0]

        expect(log_message).contains("Traceback")
        expect(log_message).contains("RuntimeError")
