"""Relative date words used by the order extractor and the synthetic generator."""

import re
from datetime import datetime, timedelta

_TODAY = re.compile(r"\b(aaj|today|tonight)\b|आज", re.IGNORECASE)
_TOMORROW = re.compile(
    r"\b(kal|tomorrow|tomrw|tmrw|tmr|tommorow|tommorrow)\b|कल",
    re.IGNORECASE,
)
_TOMORROW_LABELS = {"tomorrow", "kal", "tomrw", "tmrw", "tmr", "tommorow", "tommorrow"}
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def relative_date_label(text: str) -> str:
    """Return today, tomorrow, ambiguous, or unspecified. Never invent a day."""
    if not text:
        return "unspecified"
    iso = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if iso:
        return iso.group()
    if re.search(r"\bparso\b|परसों", text, re.I):
        return "day_after_tomorrow"
    has_today = _TODAY.search(text) is not None
    has_tomorrow = _TOMORROW.search(text) is not None
    if has_today and not has_tomorrow:
        return "today"
    if has_tomorrow and not has_today:
        return "tomorrow"
    if has_today and has_tomorrow:
        return "ambiguous"
    weekdays = [word for word in _WEEKDAYS if re.search(rf"\b{word}\b", text, re.I)]
    return weekdays[0] if len(weekdays) == 1 else "ambiguous" if weekdays else "unspecified"


def resolve_day_label(label: str, reference: datetime):
    """Resolve a day word against a clock. Unknown words stay unresolved."""
    raw = (label or "").strip().lower()
    if raw in {"today", "aaj", "tonight"}:
        return reference.date()
    if raw in _TOMORROW_LABELS:
        return (reference + timedelta(days=1)).date()
    if raw in {"parso", "day_after_tomorrow"}:
        return (reference + timedelta(days=2)).date()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None
    if raw in _WEEKDAYS:
        delta = (_WEEKDAYS[raw] - reference.weekday()) % 7
        return (reference + timedelta(days=delta)).date()
    return None
