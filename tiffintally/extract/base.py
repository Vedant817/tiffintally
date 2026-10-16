"""
Base extractor interfaces, telemetry, and the deterministic rule-based extractor.

The rules here were written against `data/synthetic/dev.jsonl` and the messages in
`tests/test_redteam2_extract.py`, never against `data/synthetic/test.jsonl`.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from tiffintally.dates import relative_date_label
from tiffintally.schema import OrderEvent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are TiffinTally, a precise home-kitchen order extractor for Indian tiffin services.
Extract structured order events from WhatsApp messages into JSON:
{
  "events": [
    {
      "customer": "Customer Name",
      "secondary_customer": "Roommate/friend or null",
      "date": "today | tomorrow | YYYY-MM-DD | day",
      "meal": "lunch | dinner | both | unspecified",
      "qty": 1,
      "items": ["thali"],
      "mods": ["no onion", "less spicy"],
      "action": "new | cancel | change | pause | payment | none",
      "payment_amount": 500.0 or null,
      "payment_note": "text note or null",
      "confidence": 0.95
    }
  ]
}

Rules:
1. Cancel: "kal lunch cancel" -> meal='lunch', action='cancel', qty=0.
2. Multi-event: "kal lunch 2, dinner skip" -> 2 events: lunch qty=2 action='new'; dinner qty=0 action='cancel'.
3. Secondary: "roommate Priya ke liye ek lunch" -> secondary_customer='Priya', meal='lunch', qty=1.
4. Pause: "Sunday off" -> meal='both', action='pause', qty=0.
5. Chit-chat: "khana bahut tasty tha" -> action='none', meal='unspecified', qty=0, items=[].
6. Payment: "500 GPay kiya" -> action='payment', meal='unspecified', payment_amount=500.0, qty=0.
7. Unsure: confidence < 0.70.
8. Dietary mods: "bina pyaaz" -> mods=['no onion']; "kam teekha"/"kam mirchi" -> mods=['less spicy']; "bina lehsun" -> mods=['no garlic']; "jain" -> mods=['jain']; "oil kam" -> mods=['less oily']; "roti nahi rice" -> mods=['roti nahi rice']. Always extract dietary constraints into 'mods'.
9. Lexical numbers: "ek"=1, "do"=2, "teen"=3, "chaar"=4, "paanch"=5. ("teen thali" -> qty=3, "do dabba" -> qty=2, "chaar roti" -> qty=4).
10. Dual-meal clauses: If lunch and dinner are both ordered (e.g. "kal lunch 1, dinner 1" or "dono time ek ek"), set meal='both', qty=1, action='new'.
11. Hindi/Devanagari: "रात" / "रात का खाना" -> meal='dinner'. "दोपहर" / "दोपहर का खाना" -> meal='lunch'."""

DEFAULT_TELEMETRY_LOG = Path("evals/telemetry.jsonl")


def telemetry_log_path() -> Path:
    """Where model-call telemetry is appended. Tests point this at a tmp path.

    Read per call so a test that sets TELEMETRY_LOG before importing still wins.
    """
    override = os.getenv("TELEMETRY_LOG")
    return Path(override) if override else DEFAULT_TELEMETRY_LOG


class ExtractionResult(BaseModel):
    events: List[OrderEvent] = Field(default_factory=list)
    model_name: str = "heuristic"
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: Optional[str] = None
    used_fallback: bool = False
    error: Optional[str] = None


def log_model_call(result: ExtractionResult):
    """Log latency and token usage for empirical audit."""
    try:
        log_path = telemetry_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "model_name": result.model_name,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "used_fallback": result.used_fallback,
            "error": result.error,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"Telemetry logging failed: {e}")


def parse_and_validate_llm_json(
    raw_json_str: str, raw_text: str, sender: str
) -> Tuple[List[OrderEvent], Optional[str]]:
    """Validate each row independently; bind identity to the parsed sender."""
    from tiffintally.model_validation import clean_model_event

    try:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json_str.strip())
        data = json.loads(cleaned)
        rows = data.get("events") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise ValueError("events must be a list")
    except (ValueError, TypeError):
        return [_review_event(sender, raw_text, "malformed_model_json")], "Malformed JSON"
    events = []
    errors = []
    for item in rows:
        if not isinstance(item, dict):
            events.append(_review_event(sender, raw_text, "invalid_model_row"))
            errors.append("invalid_model_row")
            continue
        row = clean_model_event(item)
        if row.get("invalid"):
            reason = "model_" + ",".join(row["invalid_reasons"])
            events.append(_review_event(sender, raw_text, reason))
            errors.append(reason)
            continue
        row["customer"] = sender
        row["date"] = row.get("date") or "unspecified"
        row["raw_text"] = raw_text
        try:
            event = OrderEvent(**row)
        except (ValueError, TypeError):
            events.append(_review_event(sender, raw_text, "invalid_model_schema"))
            errors.append("invalid_model_schema")
            continue
        if event.action == "payment" and _future_payment_promise(normalise(raw_text)):
            event = _review_event(sender, raw_text, "future_payment_promise")
        events.append(event)
    if not events:
        return [_review_event(sender, raw_text, "empty_model_reply")], "Empty model reply"
    return events, "; ".join(errors) or None


# --------------------------------------------------------------------------- #
# Shared vocabularies
# --------------------------------------------------------------------------- #

# Number words, Roman and Devanagari. Devanagari entries are matched as whole
# tokens: a bare substring search for "दो" also matches the "दो" inside
# "दोपहर" (afternoon), which turned one plate into two.
_NUMBER_WORDS: List[Tuple[str, int]] = [
    ("एक", 1),
    ("दो", 2),
    ("तीन", 3),
    ("चार", 4),
    ("पांच", 5),
    ("पाँच", 5),
    ("छह", 6),
    ("सात", 7),
    ("आठ", 8),
    ("नौ", 9),
    ("दस", 10),
    ("ek", 1),
    ("one", 1),
    ("do", 2),
    ("two", 2),
    ("teen", 3),
    ("three", 3),
    ("chaar", 4),
    ("char", 4),
    ("four", 4),
    ("paanch", 5),
    ("panch", 5),
    ("five", 5),
    ("chhe", 6),
    ("six", 6),
    ("saat", 7),
    ("seven", 7),
    ("aath", 8),
    ("eight", 8),
    ("nau", 9),
    ("nine", 9),
    ("das", 10),
    ("ten", 10),
]

_ROMAN_NUMBER_WORDS = [word for word, _ in _NUMBER_WORDS if word.isascii()]
_DEVA_NUMBER_WORDS = [word for word, _ in _NUMBER_WORDS if not word.isascii()]

# Devanagari vowel signs are combining marks, so Python's `\b` does not treat
# them as word characters: `\bदो\b` matches inside "दोपहर" (afternoon) and turns
# one plate into two. Guard the Devanagari words with the script block instead.
_DEVANAGARI = r"ऀ-ॿ"

_ROMAN_NUMBER_ALT = "|".join(re.escape(word) for word in _ROMAN_NUMBER_WORDS)
_DEVA_NUMBER_ALT = "|".join(re.escape(word) for word in _DEVA_NUMBER_WORDS)
_NUMBER_ALT = f"(?:{_ROMAN_NUMBER_ALT}|{_DEVA_NUMBER_ALT})"

_NUMBER_VALUE = {re.escape(word): value for word, value in _NUMBER_WORDS}

_PLATE_WORDS = ("thali", "plate", "dabba", "dabbe", "tiffin", "tiffinbox", "parcel")

# A pause is the customer saying the kitchen should stop, not an order to start.
_PAUSE_PATTERNS = [
    r"\bno\s+tiffin\s+for\s+next\s+(\d{1,2}|\w+)\s+days?\b",
    r"\bnext\s+(\d{1,2}|\w+)\s+days?\s+(?:tiffin\s+)?(?:band|off|nahi|stop)\b",
    r"\b(\d{1,2}|\w+)\s+din\s+tiffin\s+band\b",
    r"\btiffin\s+band\b",
    r"\btiffin\s+off\b",
    r"\bband\s+ra?kho\b",
    r"\b(?:lunch|dinner)?\s*(?:se\s+)?band\b",
    r"\bno\s+tiffin\b",
    r"\bpause\b",
    r"\bstop\s+tiffin\b",
    r"\btiffin\s+chhodh",
]

# Complaint / past-tense language. "lunch bahut teekha tha" is feedback, not a
# request for tomorrow's plate.
_COMPLAINT_PATTERNS = [
    r"\brefund\b",
    r"\bcomplaint\b",
    r"\bbahar\s+ab\b",
    r"\bka\b.*\bbhi\s+nahi\b.*\baaya\b",
    r"\bnot\s+received\b",
    r"\bne\s+mila\b",
    r"\bnahi\s+mila\b",
    r"\bnahi\s+aaya\b",
    r"\bka\s+nahi\s+aaya\b",
    r"\bbahut\s+(?:teekha|teekhi|teekha\s+tha|mast|accha)\b",
    r"\b(?:teekha|mast|accha|kharab)\s+tha\b",
    r"\bthank\s+you\b",
    r"\bthanks\b",
    r"\bwas\s+(?:very\s+)?(?:tasty|good|delicious|bad|spicy)\b",
    r"\bkiya\s+tha\s+na\b",
    r"\bkiya\s+tha\b.*\?",
    r"\bquestion\b",
]

_DELETED_MESSAGES = {
    "this message was deleted",
    "you deleted this message",
    "null",
    "message deleted",
    "<media omitted>",
}

_PAY_APPS = r"(?:gpay|google\s*pay|phonepe|phone\s*pe|paytm|phone\s*m|bhimpay|amazon\s*pay|okaxis|ok\s*axis)"

# Strong pay words mean money moved on their own: a payment app name, or an
# explicit statement of paying.
_STRONG_PAY_WORD = rf"(?:{_PAY_APPS}|paid|payment|pay\s+kiya|pay\s+kar\s*di)"

# Weak pay words need an amount beside them. "sent" alone is how "sent the
# address" became a payment of ₹0, and "kiya" alone is how "maine order kiya
# tha na?" lost the order behind it.
_WEAK_PAY_WORD = r"(?:sent|kiya|kar\s*diya|kar\s*dijiye|kar\s*dunga|bhej\s*di|bheja|karta)"

_PAY_WORD = rf"(?:{_STRONG_PAY_WORD}|{_WEAK_PAY_WORD})"

# Rupee amount with optional thousands separators: 1,500 / 1500 / ₹1,500.00
_AMOUNT = r"(?:rs\.?|inr|₹)?\s*(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d{2,6}(?:\.\d{1,2})?)"

# Context that turns a digit run into something other than a plate count.
_QTY_AFTER_STOP = re.compile(
    r"^\s*(?:baje|baje\s+pe|baje\s+tak|o'?clock|baje\s+ke\s+liye)", re.IGNORECASE
)
_QTY_BEFORE_STOP = re.compile(
    r"(?:flat|house|h\.?\s*no|plot|room|gate|floor|block|sector|shop|shop\s*no|pin|nr|building)"
    r"\s*$",
    re.IGNORECASE,
)

# Three scanners, because the three token kinds need different guards.
#   digits / clock times -> \b, with the time alternative first so "12:30" is
#                          consumed whole instead of leaving a bare "12"
#   Roman number words   -> \b
#   Devanagari words     -> script-block guards, because \b is unreliable there
_QTY_DIGITS = re.compile(
    r"\b(\d{1,2}:\d{2}(?::\d{2})?|\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+(?:\.\d+)?)\b"
)
_QTY_ROMAN = re.compile(rf"\b({_ROMAN_NUMBER_ALT})\b", re.IGNORECASE)
_QTY_DEVA = re.compile(
    rf"(?<![{_DEVANAGARI}])({_DEVA_NUMBER_ALT})(?![{_DEVANAGARI}])", re.IGNORECASE
)

_WEEKDAY_PATTERN = (
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|mon|tue|tues|wed|thu|thurs|fri|sat|sun)"
)

_TYPO_FIXES = [
    (r"\bdinr\b", "dinner"),
    (r"\bdnr\b", "dinner"),
    (r"\blunchh\b", "lunch"),
    (r"\bcncl\b", "cancel"),
    (r"\bcancl\b", "cancel"),
    (r"\bcancled\b", "cancel"),
    (r"\btomrw\b", "tomorrow"),
    (r"\btmrw\b", "tomorrow"),
    (r"\btmr\b", "tomorrow"),
    (r"\btommorow\b", "tomorrow"),
    (r"\btommorrow\b", "tomorrow"),
]


def normalise(text: str) -> str:
    """Lowercase and expand the typos cooks actually type."""
    lower = text.lower().strip()
    for pattern, replacement in _TYPO_FIXES:
        lower = re.sub(pattern, replacement, lower)
    return lower


def strip_whatsapp_noise(text: str) -> Tuple[str, List[str]]:
    """Remove export noise and report what was found.

    Returns the cleaned body plus flags for `edited` / `forwarded` / `deleted`.
    """
    flags: List[str] = []
    body = text.strip()

    if body.lower() in _DELETED_MESSAGES:
        return "", ["deleted"]

    if body.startswith("Forwarded") or body.startswith("‎Forwarded"):
        flags.append("forwarded")
        body = re.sub(r"^Forwarded(?:\s+many\s+times)?\s*:?\s*", "", body, flags=re.IGNORECASE)

    edited_suffix = re.search(r"<This message was edited>", body, flags=re.IGNORECASE)
    if edited_suffix:
        flags.append("edited")
        body = re.sub(r"<This message was edited>", "", body, flags=re.IGNORECASE)

    return body.strip(), flags


def _match_number(token: str) -> Optional[int]:
    """Value of a numeric or number-word token. None when it is not a quantity."""
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _NUMBER_VALUE.get(re.escape(token))


def _is_clock_time(token: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", token.strip()))


def find_quantities(text: str) -> List[Tuple[int, int, str]]:
    """All quantity candidates as (start, end, raw token), in text order.

    Clock times, "5 baje" and address numbers are excluded. Callers decide which
    candidate attaches to which meal.
    """
    found: List[Tuple[int, int, str]] = []
    scanners = (_QTY_DIGITS, _QTY_ROMAN, _QTY_DEVA)
    for scanner in scanners:
        for match in scanner.finditer(text):
            raw = match.group(1)
            if _is_clock_time(raw):
                continue
            before = text[max(0, match.start() - 24) : match.start()]
            after = text[match.end() : match.end() + 16]
            if _QTY_BEFORE_STOP.search(before) or _QTY_AFTER_STOP.search(after):
                continue
            found.append((match.start(), match.end(), raw))
    found.sort(key=lambda item: item[0])
    return found


def _meal_spans(text: str) -> List[Tuple[int, int, str]]:
    """(start, end, meal) for every lunch/dinner mention, Roman or Devanagari."""
    pattern = re.compile(
        r"\b(lunch|dinner|dopahar|dopahar\s*ka\s*khana|raat|raat\s*ka\s*khana)\b"
        r"|दोपहर"
        r"|रात",
        re.IGNORECASE,
    )
    spans: List[Tuple[int, int, str]] = []
    for match in pattern.finditer(text):
        token = match.group(1)
        if token is None:
            meal = "dinner" if "रात" in match.group(0) else "lunch"
        else:
            normalised = token.lower()
            meal = (
                "lunch"
                if "dopahar" in normalised
                else "dinner"
                if "raat" in normalised
                else normalised
            )
        spans.append((match.start(), match.end(), meal))
    return spans


def _meal_qty(text: str, meal: str) -> int:
    """Quantity attached to this meal. A number on the other meal does not carry over."""
    words = {"ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3}
    before = re.search(rf"\b(ek|one|do|two|teen|three|\d+)\s+{meal}\b", text)
    if before:
        token = before.group(1)
        return int(token) if token.isdigit() else words[token]
    after = re.search(rf"\b{meal}\s+(\d+)\b", text)
    if after:
        return int(after.group(1))
    return 1


def _nearest_quantity(
    text: str,
    spans: List[Tuple[int, int, str]],
    meal: str,
    skip: Optional[Tuple[int, int]] = None,
) -> Optional[int]:
    """The quantity closest to this meal word, in either direction, within 24 chars.

    `skip` excludes one span, so a delta's own number is not also read as the
    order it is adding to: in "+1 kal lunch" the 1 is the delta, not a base.
    """
    target = [(s, e) for s, e, m in spans if m == meal]
    if not target:
        return None
    candidates = find_quantities(text)
    best: Optional[Tuple[int, int]] = None
    for s, e in target:
        for qs, qe, raw in candidates:
            if skip and qs >= skip[0] and qe <= skip[1]:
                continue
            value = _match_number(raw)
            if value is None:
                continue
            if qe <= s and s - qe <= 24:
                distance = s - qe
            elif s <= qs and qs - e <= 24:
                distance = qs - e
            else:
                continue
            if best is None or distance < best[0]:
                best = (distance, value)
    return best[1] if best else None


def _has_plate_word(text: str) -> bool:
    return any(word in text for word in _PLATE_WORDS)


def _cancelled_meals(text: str, spans: List[Tuple[int, int, str]]) -> set[str]:
    """Bind a cancel word to the meal just before it, else the meal just after it."""
    cancels = [
        match.start()
        for match in re.finditer(r"\b(cancel|skip|nahi\s+chahiye|mat\s+bhejna|rehat)\b", text)
    ]
    bound: set[str] = set()
    for pos in cancels:
        before = [meal for start, _, meal in spans if 0 <= pos - start <= 24]
        after = [meal for start, _, meal in spans if 0 < start - pos <= 24]
        if before:
            bound.add(before[-1])
        elif after:
            bound.add(after[0])
    return bound


def _future_payment_promise(text: str) -> bool:
    """ "payment kal karunga" is a promise, not money already sent."""
    return bool(
        re.search(
            r"\b(?:payment|pay|bhej\s*di)\s+(?:kal|baad|baaki|parso|next\s+\w+|aaj\s+raat)\b",
            text,
        )
        or re.search(
            r"\bkar\s*(?:unga|denge|dungi|dunga)\b|\bbhej(?:unga|\s*dunga)\b|\bwill\s+pay\b", text
        )
    )


def _amount_near(text: str, anchors: List[int]) -> Optional[float]:
    """Amount within 40 chars after, or before, any anchor position."""
    amount_re = re.compile(_AMOUNT)

    for anchor in anchors:
        window = text[max(0, anchor - 40) : anchor]
        matches = list(amount_re.finditer(window))
        if matches:
            return float(matches[-1].group(1).replace(",", ""))
    for anchor in anchors:
        window = text[anchor : anchor + 40]
        match = amount_re.search(window)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _payment_amount(text: str) -> Optional[float]:
    """Rupees when the line is a payment. None when it is not a payment.

    A strong pay word (a payment app, or an explicit "paid") is enough on its
    own. A weak one ("sent", "kiya") needs a rupee amount beside it, so
    "sent the address" and "maine order kiya tha na?" stop swallowing orders.
    """
    strong = bool(re.search(rf"\b{_STRONG_PAY_WORD}\b", text))
    weak = bool(re.search(rf"\b{_WEAK_PAY_WORD}\b", text))
    if not strong and not weak:
        return None
    if _future_payment_promise(text):
        return None

    anchors = [m.start() for m in re.finditer(rf"\b{_PAY_WORD}\b", text)]
    amount = _amount_near(text, anchors)

    if amount is not None:
        return amount
    # App name with no readable amount: a payment happened, amount unknown.
    return 0.0 if strong else None


def _detect_pause(text: str) -> Optional[Tuple[Optional[str], Optional[str], bool]]:
    """(start_day, until_day, needs_review) when the line is a pause.

    A weekday range ("Sunday se next Thursday tak") carries both ends, so the
    reconciler can tell a genuine holiday window from a single skipped Sunday.
    """
    range_match = re.search(
        rf"\b({_WEEKDAY_PATTERN})\s+se\s+(?:next\s+)?({_WEEKDAY_PATTERN})\s+tak\b", text
    )
    if range_match:
        return range_match.group(1), range_match.group(2), True

    for pattern in _PAUSE_PATTERNS:
        if re.search(pattern, text):
            needs_review = bool(re.search(r"\b(\d{1,2}|ek|do|teen|three)\s+(?:din|days?)\b", text))
            return None, None, needs_review
    return None


def _is_complaint(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _COMPLAINT_PATTERNS)


def _fractional_quantity(text: str) -> Optional[str]:
    """The fractional phrase when the customer gave a half or 1.5 plate."""
    match = re.search(
        r"\b(half|adhoora|adha|aadha|adhi|1\.5|one\.five|1\s*\.\s*5)\s*"
        r"(plate|thali|dabba)?",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(0)
    match = re.search(
        r"(?:plate|thali|dabba)\s*(?:kitna|kitni)?\s*(?:half|adha|aadha|adhi)", text, re.IGNORECASE
    )
    return match.group(0) if match else None


def _find_delta(text: str) -> Optional[Tuple[Optional[str], Tuple[int, int]]]:
    """The ("one more", span) in a message, or None.

    Skipped when the number belongs to a side item rather than a plate: in
    "lunch 1 aur 2 roti extra" the 2 is extra roti, not a second thali.
    """
    match = re.search(
        rf"(?:\+\s*(\d{{1,2}})|(\b{_ROMAN_NUMBER_ALT}\b|\d{{1,2}})\s+(?:aur|more|or)\b)"
        rf"|\b(ek|one)\s+(?:aur|more)\b"
        rf"|\baur\s+(ek|one|1)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    start, end = match.span()
    after = text[end : end + 24]
    if re.match(r"\s*\d{0,2}\s*(roti|rotli|paratha|sabzi|chapati|piece)", after, re.IGNORECASE):
        return None
    return (match.group(1) or match.group(2) or match.group(3)), (start, end)


def _canonical_mods(text: str) -> List[str]:
    mods: List[str] = []
    if any(
        phrase in text
        for phrase in ("no onion", "bina pyaaz", "bina pyaj", "बिना प्याज", "प्याज नहीं", "jain")
    ):
        mods.append("no onion")
    if any(phrase in text for phrase in ("roti nahi rice", "no rice", "only roti", "4 roti")):
        mods.append("roti nahi rice")
    if any(
        phrase in text
        for phrase in (
            "kam teekha",
            "less spicy",
            "less spic",
            "bina mirchi",
            "no spic",
            "no spice",
        )
    ):
        mods.append("less spicy")
    if any(phrase in text for phrase in ("no curd", "replace curd", "bina dahi")):
        mods.append("no curd")
    if "extra sabzi" in text:
        mods.append("extra sabzi")
    if re.search(r"\bkadak\s+(roti|rotli)\b", text):
        mods.append("kadak roti")
    if "extra roti" in text or re.search(
        r"\b(roti|rotli)\s+vadhare\b|\bvadhare\s+(roti|rotli)\b", text
    ):
        mods.append("extra roti")

    # "2 roti extra" is a side request, not a second plate.
    extra = re.search(rf"\b(\d{{1,2}}|{_NUMBER_ALT})\s+(roti|rotli)\s+extra\b", text, re.IGNORECASE)
    if extra:
        count = _match_number(extra.group(1))
        mod = f"extra {extra.group(2)} x{count}" if count else f"extra {extra.group(2)}"
        if mod not in mods:
            mods.append(mod)
    elif "roti extra" in text and "extra roti" not in mods:
        mods.append("extra roti")
    return mods


def _dated_meal_events(text: str, sender: str, raw_text: str) -> List[OrderEvent]:
    """Split "Mon lunch 2, Tue lunch 1, Wed off" into one event per weekday.

    Returns [] unless at least two dated clauses were found, so a single
    "Monday off" still goes down the normal pause path.
    """
    pattern = re.compile(
        rf"\b({_WEEKDAY_PATTERN})\s+(?:se\s+|t tak\s+|tak\s+)?"
        rf"(lunch|dinner|dopahar|raat)\s*(?:bhej\w*\s*)?(\d{{1,2}}|{_NUMBER_ALT})?\b"
        rf"|\b({_WEEKDAY_PATTERN})\s+(?:ko\s+)?(off|band|skip|cancel|nahi)\b",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return []

    events: List[OrderEvent] = []
    for match in matches:
        if match.group(1):
            day, meal_word, qty_token = match.group(1), match.group(2), match.group(3)
            meal_word = meal_word.lower()
            meal = (
                "lunch"
                if meal_word in ("lunch", "dopahar")
                else "dinner"
                if meal_word == "raat"
                else meal_word
            )
            qty = _match_number(qty_token) if qty_token else 1
            events.append(
                OrderEvent(
                    customer=sender,
                    date=day.lower(),
                    meal=meal,
                    qty=qty,
                    items=["thali"],
                    action="new",
                    raw_text=raw_text,
                    confidence=0.85,
                )
            )
        else:
            day, word = match.group(4), match.group(5).lower()
            action = "pause" if word in ("off", "band") else "cancel"
            events.append(
                OrderEvent(
                    customer=sender,
                    date=day.lower(),
                    meal="both",
                    qty=0,
                    items=[],
                    action=action,
                    raw_text=raw_text,
                    confidence=0.85,
                )
            )
    return events


def _review_event(
    sender: str,
    raw_text: str,
    reason: str,
    date: str = "unspecified",
    confidence: float = 0.5,
) -> OrderEvent:
    """An event that carries no plate count but must reach the cook's review list."""
    return OrderEvent(
        customer=sender,
        date=date,
        meal="unspecified",
        qty=0,
        items=[],
        action="none",
        raw_text=raw_text,
        confidence=confidence,
        needs_review=True,
        audit_flags=[reason],
    )


def _heuristic_single(raw_text: str, sender: str) -> List[OrderEvent]:
    """
    Deterministic rule-based extractor for common Hinglish order phrases.

    Used as the local fallback, for offline demo mode, and for the synthetic test
    suites. Where a message is ambiguous the result is routed to review rather
    than guessed at, because a wrong plate count costs the cook food.
    """
    body, noise_flags = strip_whatsapp_noise(raw_text)

    # A deleted message has no content. Record it so the cook can see the gap.
    if "deleted" in noise_flags:
        return [
            OrderEvent(
                customer=sender,
                date="unspecified",
                meal="unspecified",
                qty=0,
                items=[],
                action="none",
                raw_text=raw_text,
                confidence=0.99,
                audit_flags=["deleted"],
            )
        ]

    lower = normalise(body)
    events: List[OrderEvent] = []
    spoken_date = relative_date_label(lower)

    def flag(ev: OrderEvent) -> OrderEvent:
        ev.audit_flags.extend(noise_flags)
        return ev

    def review(reason: str, confidence: float = 0.5) -> List[OrderEvent]:
        return [flag(_review_event(sender, raw_text, reason, spoken_date, confidence))]

    # 1. Multi-day shorthand: "Mon lunch 2, Tue lunch 1, Wed off".
    dated = _dated_meal_events(lower, sender, raw_text)
    if dated:
        for ev in dated:
            flag(ev)
        return dated

    # 2. Complaint, past tense or feedback. These describe what already happened.
    if _is_complaint(lower):
        refund_amount = None
        refund_word = re.search(r"\brefund\b|\bwaapas\b|\bpaisa\s+wapas\b", lower)
        if refund_word:
            nearby = _amount_near(lower, [refund_word.start()])
            if nearby is not None:
                refund_amount = nearby
        if refund_amount is not None:
            ev = OrderEvent(
                customer=sender,
                date="today",
                meal="unspecified",
                qty=0,
                action="payment",
                payment_amount=refund_amount,
                payment_note="refund requested",
                raw_text=raw_text,
                confidence=0.8,
                needs_review=True,
            )
            return [flag(ev)]
        return review("complaint_or_feedback")

    # 3. Fractional plates. One point five thalis is not one thali.
    fractional = _fractional_quantity(lower)
    if fractional:
        return review("fractional_quantity")

    # 4. Pause: the customer is asking the kitchen to stop, not to start.
    pause = _detect_pause(lower)
    if pause:
        start_day, until, needs_review = pause
        ev = OrderEvent(
            customer=sender,
            date=start_day or ("sunday" if "sunday" in lower else spoken_date),
            meal="both",
            qty=0,
            items=[],
            action="pause",
            raw_text=raw_text,
            confidence=0.6 if needs_review else 0.9,
            needs_review=needs_review,
            pause_until=until,
        )
        if needs_review:
            ev.audit_flags.append("pause_duration_unresolved" if until is None else "date_range")
        return [flag(ev)]

    # 5. Payments. Checked after complaints so "refund 160" is not a fresh order.
    paid = _payment_amount(lower)
    if paid is not None:
        note = "partial" if re.search(r"\b(out\s+of|baaki|remaining)\b", lower) else raw_text
        ev = OrderEvent(
            customer=sender,
            date="today",
            meal="unspecified",
            qty=0,
            action="payment",
            payment_amount=paid,
            payment_note=note,
            raw_text=raw_text,
            confidence=0.95 if paid > 0 else 0.7,
        )
        return [flag(ev)]

    # 6. Pure acknowledgements and short replies. A thumbs-up to the cook's
    # "kal lunch chahiye?" is an answer, not silence, so it goes to review.
    if re.fullmatch(r"[\s\U0001f600-\U0001f9ff👍✅🙏❤\U0001f44d\U0001f44f\U0001f44d]+", body):
        return review("reply_to_check", confidence=0.6)
    if re.fullmatch(r"\s*(haan|ha|ji|ok|okay|yes|nahi|nope|thanks|thank\s*you)\s*[.!]?\s*", lower):
        if re.search(r"\b(nahi|no)\b", lower):
            return review("reply_to_check", confidence=0.6)
        if not _has_plate_word(lower) and not _meal_spans(lower):
            return review("reply_to_check", confidence=0.6)

    # 7. Chit-chat and compliments about food that is not being ordered.
    chitchat_terms = [
        "thank you",
        "dhanyawad",
        "khana mast",
        "tasty",
        "delicious",
        "good night",
        "menu kya hai",
        "swadisht",
    ]
    if any(term in lower for term in chitchat_terms) and not any(
        k in lower for k in ["bhejo", "plate", "thali", "cancel"]
    ):
        ev = OrderEvent(
            customer=sender,
            date="today",
            meal="unspecified",
            qty=0,
            items=[],
            action="none",
            raw_text=raw_text,
            confidence=0.99,
        )
        return [flag(ev)]

    meal_spans = _meal_spans(lower)
    meals_present = {meal for _, _, meal in meal_spans}
    has_lunch = "lunch" in meals_present
    has_dinner = "dinner" in meals_present
    cancel_words = re.search(r"\b(cancel|skip|nahi\s+chahiye|mat\s+bhejna|rehat)\b", lower)
    has_cancel = bool(cancel_words)

    # Devanagari "nahin" is a negation, not a cancellation.
    devanagari_nahin = re.search(r"नहीं|नही", lower)

    if not meal_spans and not _has_plate_word(lower) and not has_cancel:
        if devanagari_nahin:
            return review("devanagari_mod_only")
        return [
            flag(
                OrderEvent(
                    customer=sender,
                    date=spoken_date,
                    meal="unspecified",
                    qty=0,
                    items=[],
                    action="none",
                    raw_text=raw_text,
                    confidence=0.99,
                )
            )
        ]

    mods = _canonical_mods(lower)

    # Secondary customer: "roommate Priya ke liye bhi ek" is one plate more.
    secondary_cust = None
    sec_match = re.search(
        r"(?:roommate|friend|dost)\s+([A-Za-z]+)\s+ke liye\s+(?:bhi\s+)?(?:ek|1)?",
        raw_text,
        re.IGNORECASE,
    )
    if sec_match:
        secondary_cust = sec_match.group(1).title()

    # An order change: "change it to 3", "2 nahi 3".
    quantity_correction = re.search(r"\d+\s+nahi\s+\d+", lower)
    if "change" in lower or quantity_correction:
        change_match = re.findall(r"\d+", lower)
        new_qty = int(change_match[-1]) if change_match else 1
        meal = "dinner" if has_dinner and not has_lunch else "lunch"
        ev = OrderEvent(
            customer=sender,
            date=spoken_date,
            meal=meal,
            qty=new_qty,
            items=["thali"],
            mods=mods,
            action="change",
            raw_text=raw_text,
            confidence=0.9,
            secondary_customer=secondary_cust,
        )
        return [flag(ev)]

    cancelled = _cancelled_meals(lower, meal_spans) if has_cancel else set()

    # Both meals named in one message: one event per meal.
    if has_lunch and has_dinner:
        for meal_name in ("lunch", "dinner"):
            is_cancelled = meal_name in cancelled
            qty = 0 if is_cancelled else (_nearest_quantity(lower, meal_spans, meal_name) or 1)
            events.append(
                OrderEvent(
                    customer=sender,
                    date=spoken_date,
                    meal=meal_name,
                    qty=qty,
                    items=[] if is_cancelled else ["thali"],
                    mods=[] if is_cancelled else mods,
                    action="cancel" if is_cancelled else "new",
                    raw_text=raw_text,
                    secondary_customer=secondary_cust,
                    confidence=0.9,
                )
            )
        for ev in events:
            flag(ev)
        return events

    # A delta: "ek aur", "one more", "+1". This adds a plate to what is already
    # ordered. Read as a fresh order it replaced the count instead, so "lunch 2"
    # followed by "kal lunch ek aur" left one plate on the sheet.
    delta = _find_delta(lower)
    if delta:
        token, span = delta
        count = _match_number(token) if token else 1
        meal = meal_spans[0][2] if meal_spans else "lunch"
        base_qty = _nearest_quantity(lower, meal_spans, meal, skip=span) if meal_spans else None

        if base_qty:
            # "lunch 2, aur ek" is one message for three plates, not a separate
            # instruction to add one to an order we have not seen.
            action, qty = "new", base_qty + (count or 0)
        else:
            action, qty = "add", count or 1

        ev = OrderEvent(
            customer=sender,
            date=spoken_date,
            meal=meal,
            qty=qty,
            items=["thali"],
            mods=mods,
            action=action,
            raw_text=raw_text,
            secondary_customer=secondary_cust,
            confidence=0.85,
        )
        return [flag(ev)]

    # A single meal, or a bare plate count.
    if meal_spans:
        meal = meal_spans[0][2]
    else:
        meal = "dinner" if has_dinner else "lunch"

    if has_cancel or meal in cancelled:
        ev = OrderEvent(
            customer=sender,
            date=spoken_date,
            meal=meal,
            qty=0,
            items=[],
            mods=[],
            action="cancel",
            raw_text=raw_text,
            confidence=0.9,
            secondary_customer=secondary_cust,
        )
        return [flag(ev)]

    if meal_spans:
        qty = _nearest_quantity(lower, meal_spans, meal)
    else:
        quantities = find_quantities(lower)
        values = [_match_number(raw) for _, _, raw in quantities]
        values = [v for v in values if v is not None]
        qty = max(values) if values else None

    if qty is None:
        qty = 1
    elif secondary_cust and re.search(r"\bbhi\b", lower) and qty == 1:
        # "roommate Priya ke liye bhi ek" is a second plate, not a replacement.
        qty = 2

    ev = OrderEvent(
        customer=sender,
        date=spoken_date,
        meal=meal,
        qty=qty,
        items=["thali"],
        mods=mods,
        action="new",
        raw_text=raw_text,
        secondary_customer=secondary_cust,
        confidence=0.9 if qty else 0.7,
    )
    return [flag(ev)]


def heuristic_extract(raw_text: str, sender: str) -> List[OrderEvent]:
    """Retain both intents in a message containing an order and a payment."""
    events = _heuristic_single(raw_text, sender)
    lower = normalise(raw_text)
    if any(
        event.action == "payment" and not event.needs_review for event in events
    ) and _meal_spans(lower):
        order_text = re.sub(_AMOUNT, " ", lower)
        order_text = re.sub(rf"\b{_PAY_WORD}\b", " ", order_text)
        orders = _heuristic_single(order_text, sender)
        for event in orders:
            event.raw_text = raw_text
        events = [event for event in orders if event.action not in {"none", "payment"}] + events
    return events
