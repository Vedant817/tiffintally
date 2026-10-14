"""Relative date words used by the order extractor and the synthetic generator."""

import re

_TODAY = re.compile(r"\b(aaj|today|tonight)\b|आज", re.IGNORECASE)
_TOMORROW = re.compile(r"\b(kal|tomorrow)\b|कल", re.IGNORECASE)


def relative_date_label(text: str) -> str:
    """Return today, tomorrow, ambiguous, or unspecified. Never invent a day."""
    if not text:
        return "unspecified"
    has_today = _TODAY.search(text) is not None
    has_tomorrow = _TOMORROW.search(text) is not None
    if has_today and not has_tomorrow:
        return "today"
    if has_tomorrow and not has_today:
        return "tomorrow"
    if has_today and has_tomorrow:
        return "ambiguous"
    return "unspecified"
