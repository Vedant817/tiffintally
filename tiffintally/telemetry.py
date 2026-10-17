"""
Optional Sentry tracing. Customer message text is not attached to events.
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
_SECRET_HINTS = ("api_key", "authorization", "token", "password", "secret", "dsn")


def _scrub_event(event, hint):
    """Drop message text and anything that looks like a credential before send."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers):
                if any(hint_name in key.lower() for hint_name in _SECRET_HINTS):
                    headers[key] = "[redacted]"
    extra = event.get("extra")
    if isinstance(extra, dict):
        extra.pop("raw_text_preview", None)
        extra.pop("raw_text", None)
    return event


def _scrub_breadcrumb(crumb, hint):
    data = crumb.get("data")
    if isinstance(data, dict):
        for key in ("raw_text", "body", "message", "input"):
            if key in data:
                data[key] = "[redacted]"
    return crumb


def telemetry_enabled() -> bool:
    """False when TIFFINTALLY_TELEMETRY is 0/false/no. Tests run with it off."""
    flag = os.getenv("TIFFINTALLY_TELEMETRY", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


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

    if not telemetry_enabled():
        logger.info("TIFFINTALLY_TELEMETRY is off; Sentry not initialized.")
        return False

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
            # Replaces the deprecated send_default_pii=False. No user info,
            # cookies, headers, query strings, or HTTP bodies.
            data_collection={
                "user_info": False,
                "cookies": {"mode": "off"},
                "http_headers": {"request": {"mode": "off"}},
                "url_query_params": {"mode": "off"},
                "http_bodies": [],
                "gen_ai": {"inputs": False, "outputs": False},
                "stack_frame_variables": False,
                "frame_context_lines": 0,
            },
            before_send=_scrub_event,
            before_breadcrumb=_scrub_breadcrumb,
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
def trace_span(
    op: str, name: str, data: Optional[dict[str, Any]] = None
) -> Generator[Optional[Any], None, None]:
    """
    Context manager to trace critical pipeline stages:
    - audio.transcription
    - guardrail.sanitization
    - llm.extraction
    - reconcile.orders
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
            scope_mgr = (
                sentry_sdk.isolation_scope
                if hasattr(sentry_sdk, "isolation_scope")
                else sentry_sdk.push_scope
            )
            with scope_mgr() as scope:
                scope.set_level("warning")
                scope.set_tag("security_incident", "prompt_injection")
                scope.set_extra("flags", flags)
                scope.set_extra("text_length", len(raw_text or ""))
                scope.set_tag("customer_attached", "no")
                sentry_sdk.capture_message(
                    f"TiffinTally Guardrail Alert: {', '.join(flags)} detected",
                    level="warning",
                )
        except Exception as e:
            logger.debug("Failed sending guardrail alert to Sentry: %s", e)


def record_metric(
    name: str, value: float, unit: str = "none", tags: Optional[dict[str, str]] = None
) -> None:
    """Record key metrics: latency, token counts, plate waste saved, marginal AI cost."""
    logger.info("METRIC [%s]: %.2f %s (tags=%s)", name, value, unit, tags)
    if HAS_SENTRY:
        try:
            if hasattr(sentry_sdk, "metrics"):
                sentry_sdk.metrics.distribution(name, value, unit=unit, tags=tags)
        except Exception:
            pass
