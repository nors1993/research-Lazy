"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict

from ..config import settings


def add_log_level(
    logger: structlog.stdlib.BoundLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add the log level to the event dict."""
    event_dict["level"] = method_name
    return event_dict


def add_timestamp(
    logger: structlog.stdlib.BoundLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add timestamp to the event dict."""
    event_dict["timestamp"] = event_dict.get("timestamp")
    return event_dict


def configure_logging() -> None:
    """Configure structured logging based on settings."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add JSON rendering in production, console in development
    if settings.log_format == "json" or settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        **initial_context: Initial context to bind to the logger

    Returns:
        Configured structlog logger
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


# Initialize logging on module import
configure_logging()

# Create default logger for module-level logging
logger = get_logger(__name__)
