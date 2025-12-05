from unittest.mock import Mock

from django.http import HttpRequest

import pytest

from tab.core.middleware import DomainRedirectMiddleware, ExceptionLoggingMiddleware


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
        mock_logger = mocker.patch("tab.core.middleware.log")
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
        mock_logger = mocker.patch("tab.core.middleware.log")
        exception = RuntimeError("Runtime error")

        try:
            raise exception
        except RuntimeError:
            middleware.process_exception(http_request, exception)

        call_args = mock_logger.critical.call_args
        log_message = call_args[0][0]

        expect(log_message).contains("Traceback")
        expect(log_message).contains("RuntimeError")


def describe_domain_redirect_middleware():
    @pytest.fixture
    def middleware():
        return DomainRedirectMiddleware(get_response=Mock())

    @pytest.fixture
    def http_request():
        r = HttpRequest()
        r.method = "GET"
        r.path = "/test-path/"
        r.get_host = Mock(return_value="test-analysis-bot.example.com")  # type: ignore[method-assign]
        r.get_full_path = Mock(return_value="/test-path/")  # type: ignore[method-assign]
        return r

    def it_redirects_from_legacy_domain(
        expect, mocker, middleware, http_request, settings
    ):
        settings.ALLOWED_HOSTS = [
            "localhost",
            "test-analysis-bot.example.com",
        ]
        mock_logger = mocker.patch("tab.core.middleware.log")
        result = middleware.process_request(http_request)
        expect(mock_logger.warning.called).is_(True)
        call_args = mock_logger.warning.call_args
        log_message = call_args[0][0]
        expect(log_message).contains(
            "Redirecting from test-analysis-bot.example.com/test-path/ to http://testserver.com/test-path/"
        )
        expect(result).is_not(None)
        expect(result.status_code) == 301
