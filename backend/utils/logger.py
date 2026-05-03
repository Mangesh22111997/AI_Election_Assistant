"""
backend/utils/logger.py
────────────────────────
Structured logging using structlog + Google Cloud Logging.
Every log entry includes: timestamp, level, module, and context fields.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from backend.config import get_settings

settings = get_settings()


def _add_app_context(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject application-level context into every log entry."""
    event_dict.setdefault("app", "election-guide-assistant")
    event_dict.setdefault("env", settings.app_env)
    return event_dict


def _drop_color_message_key(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove the colour-message key added by uvicorn."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """Configure structlog with JSON rendering (production) or pretty (dev)."""
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_app_context,
        _drop_color_message_key,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Optional: Google Cloud Logging
    if settings.is_production:
        try:
            import google.cloud.logging as gcp_logging

            client = gcp_logging.Client()
            client.setup_logging(log_level=getattr(logging, settings.log_level))
        except Exception:
            pass  # GCP logging is best-effort


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a named structlog bound logger."""
    return structlog.get_logger(name)


# ── Audit Logger ─────────────────────────────────────────────────────────────
# Separate logger dedicated to compliance audit events.
audit_logger = get_logger("audit")


def log_interaction(
    *,
    user_id: str,
    query: str,
    intent: str,
    guide_latency_ms: int,
    simplifier_latency_ms: int,
    safety_result: str,
    violation_type: str | None,
    sources_used: list[str],
    user_feedback: str | None = None,
) -> None:
    """Write a structured audit log entry for every user interaction."""
    audit_logger.info(
        "interaction",
        user_id=user_id,
        query="[REDACTED]",           # Never log raw PII/queries
        query_length=len(query),
        intent_classification=intent,
        guide_agent_latency_ms=guide_latency_ms,
        simplifier_agent_latency_ms=simplifier_latency_ms,
        safety_check_result=safety_result,
        violation_type=violation_type,
        sources_used=sources_used,
        user_feedback=user_feedback,
    )
