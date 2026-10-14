"""
Production Telemetry and Distributed Pipeline Tracing for TiffinTally.
Powered by Sentry SDK for AI agent monitoring, latency tracing,
guardrail security incident alerting, and kitchen economic metrics.
Qualifies for Sentry Hackathon Partner Prize ($100).
"""

import contextlib
import logging
import os
import time
from typing import Any, Generator, Optional

try:
    import sentry_sdk
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False

logger = logging.getLogger("tiffintally.telemetry")

_INITIALIZED = False


def init_telemetry(
    dsn: Optional[str] = None,
    environment: str = "production",
    traces_sample_rate: float = 1.0,
) -> bool:
    """
    Initialize Sentry SDK with distributed tracing and AI pipeline breadcrumbs.
    If no DSN is provided and SENTRY_DSN env var is missing, logs gracefully without crashing.
    """
    global _INITIALIZED
    target_dsn = dsn or os.getenv("SENTRY_DSN")

    if not HAS_SENTRY:
        logger.info("sentry-sdk not available; telemetry using local logger.")
        return False

    if not target_dsn:
        logger.info("SENTRY_DSN not configured; distributed tracing running in local mode.")
        _INITIALIZED = True
        return False

    try:
        sentry_sdk.init(
            dsn=target_dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            release="tiffintally@0.2.0",
        )
        sentry_sdk.set_tag("app", "tiffintally")
        sentry_sdk.set_tag("domain", "home_kitchen_automation")
        _INITIALIZED = True
        logger.info("Sentry telemetry successfully initialized.")
        return True
    except Exception as e:
        logger.warning("Failed to initialize Sentry: %s", e)
        return False


@contextlib.contextmanager
def trace_span(op: str, name: str, data: Optional[dict[str, Any]] = None) -> Generator[Optional[Any], None, None]:
    """
    Context manager to trace critical pipeline stages:
    - audio.transcription
    - guardrail.sanitization
    - llm.extraction
    - reconcile.orders
    - forecast.tabpfn
    """
    start_time = time.perf_counter()
    sentry_span = None

    if HAS_SENTRY:
        try:
            sentry_span = sentry_sdk.start_span(op=op, name=name)
            if sentry_span and data:
                for k, v in data.items():
                    sentry_span.set_data(k, v)
        except Exception:
            sentry_span = None

    try:
        yield sentry_span
    except Exception as exc:
        if HAS_SENTRY:
            sentry_sdk.capture_exception(exc)
        logger.exception("Error during traced span '%s' (%s): %s", op, name, exc)
        raise
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.debug("Span [%s] '%s' completed in %.2f ms", op, name, latency_ms)
        if sentry_span:
            try:
                sentry_span.set_data("latency_ms", latency_ms)
                sentry_span.finish()
            except Exception:
                pass


def capture_guardrail_incident(raw_text: str, flags: list[str], customer: str = "Unknown") -> None:
    """Record prompt injection or adversarial attacks as security incidents."""
    logger.warning("SECURITY GUARDRAIL TRIGGERED: %s from customer '%s'", flags, customer)
    if HAS_SENTRY:
        try:
            # Scope isolation in modern Sentry SDK
            scope_mgr = sentry_sdk.isolation_scope if hasattr(sentry_sdk, "isolation_scope") else sentry_sdk.push_scope
            with scope_mgr() as scope:
                scope.set_level("warning")
                scope.set_tag("security_incident", "prompt_injection")
                scope.set_extra("customer", customer)
                scope.set_extra("flags", flags)
                scope.set_extra("raw_text_preview", raw_text[:200])
                sentry_sdk.capture_message(
                    f"TiffinTally Guardrail Alert: {', '.join(flags)} detected",
                    level="warning",
                )
        except Exception as e:
            logger.debug("Failed sending guardrail alert to Sentry: %s", e)


def record_metric(name: str, value: float, unit: str = "none", tags: Optional[dict[str, str]] = None) -> None:
    """Record key metrics: latency, token counts, plate waste saved, marginal AI cost."""
    logger.info("METRIC [%s]: %.2f %s (tags=%s)", name, value, unit, tags)
    if HAS_SENTRY:
        try:
            if hasattr(sentry_sdk, "metrics"):
                sentry_sdk.metrics.distribution(name, value, unit=unit, tags=tags)
        except Exception:
            pass
