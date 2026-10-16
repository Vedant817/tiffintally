"""Structured logging system for TiffinTally.

Provides dual console + rotating file logging for observability,
request tracing, and forensic debugging of failure scenarios.
"""

from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

LOGS_DIR = Path("logs")
APP_LOG_PATH = LOGS_DIR / "tiffintally.log"
FAILURE_LOG_PATH = LOGS_DIR / "failures.log"

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Initialize structured logging to console, app.log, and failures.log."""
    global _CONFIGURED
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("tiffintally")
    if _CONFIGURED:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler (clean stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Application Rotating File Handler (up to 5MB x 3 backups)
    app_file_handler = RotatingFileHandler(
        APP_LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    app_file_handler.setLevel(logging.DEBUG)
    app_file_handler.setFormatter(formatter)
    logger.addHandler(app_file_handler)

    # Dedicated Failure / Incident Log Handler (WARNING, ERROR, CRITICAL)
    fail_file_handler = RotatingFileHandler(
        FAILURE_LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fail_file_handler.setLevel(logging.WARNING)
    fail_file_handler.setFormatter(formatter)
    logger.addHandler(fail_file_handler)

    _CONFIGURED = True
    logger.info(
        "Structured logging initialized: outputting to %s and %s", APP_LOG_PATH, FAILURE_LOG_PATH
    )
    return logger


def get_logger(name: str = "tiffintally") -> logging.Logger:
    """Return a logger configured under the tiffintally namespace."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(f"tiffintally.{name}" if name != "tiffintally" else name)


def log_failure(
    event_type: str,
    message: str,
    exc: Optional[BaseException] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an operational failure with structured context and stack trace."""
    logger = get_logger("failure")
    details = f"[{event_type}] {message}"
    if extra:
        details += f" | context: {extra}"
    if exc:
        details += f"\nException: {exc}\nTraceback:\n{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"
    logger.error(details)
