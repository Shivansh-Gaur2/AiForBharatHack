"""Structured JSON logging configuration.

Produces machine-parseable log lines that work well with CloudWatch
Logs Insights, Datadog, and ELK stack.  Each log entry carries:

- ``timestamp`` — ISO-8601 UTC
- ``level`` — DEBUG / INFO / WARNING / ERROR / CRITICAL
- ``logger`` — dotted module path
- ``message`` — human text
- ``request_id`` — correlation ID injected by middleware
- ``service`` — service name (set once at startup)

Usage in a service ``main.py``::

    from services.shared.observability import configure_logging
    configure_logging(service_name="profile-service", level="INFO")
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Module-level context — set via ``configure_logging()``
_service_name: str = "unknown"
_request_id_var: str = ""


def set_request_id(request_id: str) -> None:
    """Called by request-tracing middleware on each request."""
    global _request_id_var  # noqa: PLW0603
    _request_id_var = request_id


def get_request_id() -> str:
    return _request_id_var


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": _service_name,
        }
        if _request_id_var:
            log_entry["request_id"] = _request_id_var
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Extra fields attached by domain code
        for key in ("profile_id", "tracking_id", "event_type", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


def configure_logging(
    service_name: str,
    level: str = "INFO",
    *,
    json_output: bool = True,
) -> None:
    """Bootstrap logging for a microservice.

    Parameters
    ----------
    service_name:
        Identifies the service in every log line.
    level:
        Root log level (DEBUG / INFO / WARNING / ERROR).
    json_output:
        When ``True`` (default), uses :class:`JSONFormatter`.
        Set to ``False`` for human-friendly console output during
        local debugging.
    """
    global _service_name  # noqa: PLW0603
    _service_name = service_name

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers (e.g. basicConfig from earlier imports)
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for name in ("botocore", "urllib3", "uvicorn.access", "mangum"):
        logging.getLogger(name).setLevel(logging.WARNING)
