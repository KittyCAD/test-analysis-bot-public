import json
import logging
import sys

import pytest

from tab.core.logging import JSONFormatter


def describe_json_formatter(expect):
    @pytest.fixture
    def formatter():
        return JSONFormatter()

    def it_formats_simple_messages_as_json(formatter):
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Simple error message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)

        # Parse the JSON output
        log_data = json.loads(formatted)

        expect(log_data["level"]) == "ERROR"
        expect(log_data["message"]) == "Simple error message"
        expect(log_data["logger"]) == "test.logger"

    def it_includes_exception_info_in_separate_field(formatter):
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="An error occurred",
            args=(),
            exc_info=exc_info,
        )
        formatted = formatter.format(record)

        # Parse the JSON output
        log_data = json.loads(formatted)

        expect(log_data["level"]) == "ERROR"
        expect(log_data["message"]) == "An error occurred"
        expect("exception" in log_data).is_(True)
        expect(log_data["exception"]["type"]) == "ValueError"
        expect(log_data["exception"]["value"]) == "Test exception"
        expect("traceback" in log_data["exception"]).is_(True)
        expect(isinstance(log_data["exception"]["traceback"], list)).is_(True)

    def it_outputs_single_line_json(formatter):
        try:
            raise RuntimeError("Multi-line\nerror\nmessage")
        except RuntimeError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/app/test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        formatted = formatter.format(record)

        # Verify it's a single line (no actual newlines in JSON string)
        expect("\n" in formatted).is_(False)

        # Verify it's valid JSON
        log_data = json.loads(formatted)
        expect(log_data).isinstance(dict)

    def it_includes_location_info(formatter):
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/app/views.py",
            lineno=123,
            msg="Info message",
            args=(),
            exc_info=None,
        )
        record.funcName = "my_function"

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        expect(log_data["file"]) == "/app/views.py"
        expect(log_data["line"]) == 123
        expect(log_data["function"]) == "my_function"
