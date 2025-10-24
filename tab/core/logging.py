import json
import logging
import traceback
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON logging formatter that outputs structured logs for log aggregation systems.

    This formatter outputs logs as JSON with separate fields for the message,
    exception info, and stack trace. This allows log aggregation systems like
    Axiom to properly display multi-line stack traces in their UI while keeping
    each log entry as a single line.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "value": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields from the record
        if hasattr(record, "funcName"):
            log_data["function"] = record.funcName
        if hasattr(record, "lineno"):
            log_data["line"] = record.lineno
        if hasattr(record, "pathname"):
            log_data["file"] = record.pathname

        # Return as a single-line JSON string
        return json.dumps(log_data, ensure_ascii=False)
