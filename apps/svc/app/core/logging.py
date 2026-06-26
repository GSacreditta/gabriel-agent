"""Structured JSON logging for Cloud Logging.

Cloud Run captures stdout/stderr and forwards to Cloud Logging. When the log
line is valid JSON with conventional keys (`severity`, `message`), Cloud Logging
parses it as a structured entry instead of a text blob. Use structlog to
produce those entries.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Idempotent — safe to call multiple times."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Cloud Logging recognises `severity` (uppercased level).
            _rename_level_to_severity,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def _rename_level_to_severity(_logger, _name, event_dict):
    if "level" in event_dict:
        event_dict["severity"] = event_dict.pop("level").upper()
    return event_dict


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
