"""Structured JSON logging with sensitive credential redaction and correlation ID context."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Regular expression to match sensitive tokens/passwords in string messages
SENSITIVE_PATTERNS = [
    (re.compile(r'("password"\s*:\s*)"[^"]*"', re.IGNORECASE), r'\1"***REDACTED***"'),
    (re.compile(r'("access_token"\s*:\s*)"[^"]*"', re.IGNORECASE), r'\1"***REDACTED***"'),
    (re.compile(r'("refresh_token"\s*:\s*)"[^"]*"', re.IGNORECASE), r'\1"***REDACTED***"'),
    (
        re.compile(r"(Bearer\s+)[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", re.IGNORECASE),
        r"\1***REDACTED***",
    ),
]


def redact_sensitive_data(text: str) -> str:
    """Mask credentials and tokens from log output."""
    for pattern, repl in SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def get_correlation_id() -> str | None:
    return correlation_id_ctx.get()


def set_correlation_id(corr_id: str) -> None:
    correlation_id_ctx.set(corr_id)


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter with automated credential redaction."""

    def format(self, record: logging.LogRecord) -> str:
        raw_message = record.getMessage()
        safe_message = redact_sensitive_data(raw_message)

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": safe_message,
            "correlation_id": get_correlation_id(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            # Redact sensitive keys in extra fields
            clean_extras = {}
            for k, v in record.extra_fields.items():
                if any(s in k.lower() for s in ["password", "token", "secret", "auth", "key"]):
                    clean_extras[k] = "***REDACTED***"
                else:
                    clean_extras[k] = v
            log_entry.update(clean_extras)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Initialize structured JSON logger."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]

    return root_logger
