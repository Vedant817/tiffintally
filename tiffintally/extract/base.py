"""
Base extractor interfaces, telemetry, and deterministic rule-based extractor.
"""

import json
import logging
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

TELEMETRY_LOG = Path("evals/telemetry.jsonl")


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
        TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "model_name": result.model_name,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "used_fallback": result.used_fallback,
            "error": result.error,
        }
        with open(TELEMETRY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"Telemetry logging failed: {e}")


def parse_and_validate_llm_json(
    raw_json_str: str, raw_text: str, sender: str
) -> Tuple[List[OrderEvent], Optional[str]]:
    """Safely parse LLM output JSON, with validation and fallback on malformed JSON."""
    try:
        cleaned = raw_json_str.strip()
        # Strip markdown json codeblocks if present
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        data = json.loads(cleaned)
        events_data = data.get("events", [])
        events = []
        for item in events_data:
            cust = item.get("customer") or sender
            # Normalize action
            action = item.get("action", "new")
            if action not in ["new", "cancel", "change", "pause", "payment", "none"]:
                action = "new"

            event = OrderEvent(
                customer=cust,
                secondary_customer=item.get("secondary_customer"),
                date=item.get("date") or "unspecified",
                meal=item.get("meal", "lunch"),
                qty=int(item.get("qty", 1) if action != "cancel" else 0),
                items=item.get("items", ["thali"]),
                mods=item.get("mods", []),
                action=action,
                payment_amount=item.get("payment_amount"),
                payment_note=item.get("payment_note"),
                confidence=float(item.get("confidence", 0.9)),
                raw_text=raw_text,
            )
            events.append(event)

        if events:
            return events, None

    except Exception as parse_err:
        logger.warning(f"LLM JSON parsing failed: {parse_err}")

    # Fallback: Malformed JSON -> route to review with confidence=0.30
    fallback_event = OrderEvent(
        customer=sender,
        date=relative_date_label(raw_text),
        meal="unspecified",
        qty=0,
        action="none",
        confidence=0.30,
        raw_text=f"[Review Needed] {raw_text}",
    )
    return [fallback_event], "Malformed JSON: routed to human review"


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


def _cancelled_meals(text: str) -> set[str]:
    """Bind a cancel word to the meal just before it, else the meal just after it."""
    meals = [(match.start(), match.group(1)) for match in re.finditer(r"\b(lunch|dinner)\b", text)]
    cancels = [
        match.start() for match in re.finditer(r"\b(cancel|skip|nahi chahiye|mat bhejna)\b", text)
    ]
    bound: set[str] = set()
    for pos in cancels:
        before = [meal for meal in meals if 0 <= pos - meal[0] <= 24]
        after = [meal for meal in meals if 0 < meal[0] - pos <= 24]
        if before:
            bound.add(max(before, key=lambda meal: meal[0])[1])
        elif after:
            bound.add(min(after, key=lambda meal: meal[0])[1])
    return bound


def _canonical_mods(text: str) -> List[str]:
    mods: List[str] = []
    if any(
        phrase in text for phrase in ("no onion", "bina pyaaz", "bina pyaj", "बिना प्याज", "jain")
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
    return mods


def heuristic_extract(raw_text: str, sender: str) -> List[OrderEvent]:
    """
    High-accuracy deterministic rule-based extractor for common Hinglish order phrases.
    Used for instant local fallback, offline demo mode, and synthetic test suites.
    """
    lower = raw_text.lower().strip()
    for pattern, replacement in (
        (r"\bdinr\b", "dinner"),
        (r"\bcncl\b", "cancel"),
        (r"\bcancl\b", "cancel"),
        (r"\btomrw\b", "tomorrow"),
        (r"\btmrw\b", "tomorrow"),
        (r"\btmr\b", "tomorrow"),
        (r"\btommorow\b", "tomorrow"),
        (r"\btommorrow\b", "tomorrow"),
    ):
        lower = re.sub(pattern, replacement, lower)
    events: List[OrderEvent] = []
    spoken_date = relative_date_label(lower)

    # 1. Pure chit-chat / compliments
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
        return [
            OrderEvent(
                customer=sender,
                date="today",
                meal="unspecified",
                qty=0,
                action="none",
                raw_text=raw_text,
                confidence=0.99,
            )
        ]

    # 2. Payment confirmations
    pay_matches = re.findall(
        r"(?:rs\.?|inr|₹)?\s*(\d{2,5})\s*(?:gpay|phonepe|paytm|sent|kiya|transfer)", lower
    )
    if pay_matches or "gpay kiya" in lower or "phonepe" in lower:
        amt = float(pay_matches[0]) if pay_matches else 0.0
        return [
            OrderEvent(
                customer=sender,
                date="today",
                meal="unspecified",
                qty=0,
                action="payment",
                payment_amount=amt,
                payment_note=raw_text,
                raw_text=raw_text,
                confidence=0.99,
            )
        ]

    # 3. Pauses (Sunday off, pause tiffin, next week off).
    # "not going home" is a trip negation, not a pause.
    trip_away = any(k in lower for k in ("going home", "out of station")) and not re.search(
        r"\bnot going home\b|\bnahi ja\b", lower
    )
    if any(k in lower for k in ("sunday off", "pause", "band rakhna", "stop tiffin")) or trip_away:
        range_match = re.search(
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+se\s+"
            r"(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+tak\b",
            lower,
        )
        is_range = range_match is not None
        return [
            OrderEvent(
                customer=sender,
                date=range_match.group(1)
                if is_range
                else ("sunday" if "sunday" in lower else spoken_date),
                meal="both",
                qty=0,
                action="pause",
                raw_text=raw_text,
                confidence=0.7 if is_range else 0.95,
                needs_review=is_range,
                audit_flags=["date_range"] if is_range else [],
                pause_until=range_match.group(2) if is_range else None,
            )
        ]

    # 4. Check for compound lunch + dinner messages: e.g. "kal lunch 2, dinner skip"
    has_lunch = "lunch" in lower or "dopahar" in lower or "दोपहर" in lower
    has_dinner = "dinner" in lower or "raat" in lower or "रात" in lower
    has_cancel = any(
        k in lower for k in ["cancel", "skip", "mat bhejna", "nahi chahiye", "नहीं", "कैंसिल"]
    )

    # Extract quantity (default 1)
    qty = 1
    # Check digits
    digit_match = re.search(r"\b(\d{1,2})\b", lower)
    if digit_match:
        qty = int(digit_match.group(1))
    elif "दो" in lower or re.search(r"\b(do|two)\b", lower):
        qty = 2
    elif "teen" in lower or "तीन" in lower or "three" in lower:
        qty = 3
    elif "char" in lower or "चार" in lower or "four" in lower:
        qty = 4

    mods = _canonical_mods(lower)

    # Secondary customer split check: e.g. "roommate Priya ke liye bhi ek"
    secondary_cust = None
    sec_match = re.search(
        r"(?:roommate|friend|dost)\s+([A-Za-z]+)\s+ke liye\s+(?:bhi\s+)?(?:ek|1)?", raw_text, re.I
    )
    if sec_match:
        secondary_cust = sec_match.group(1).title()
        # "bhi ek" is one more plate, not a replacement of the sender's plate.
        if re.search(r"\bbhi\b", lower):
            qty += 1

    # Order change case: "change it to 3", "2 nahi 3". "nahi chahiye" is a cancel.
    quantity_correction = re.search(r"\d+\s+nahi\s+\d+", lower)
    if "change" in lower or quantity_correction:
        # Check if change to higher number
        change_match = re.findall(r"\d+", lower)
        new_qty = int(change_match[-1]) if change_match else qty
        events.append(
            OrderEvent(
                customer=sender,
                date=spoken_date,
                meal="dinner" if has_dinner else "lunch",
                qty=new_qty,
                items=["thali"],
                mods=mods,
                action="change",
                raw_text=raw_text,
                confidence=0.90,
            )
        )
        return events

    if has_lunch and has_dinner:
        cancelled = _cancelled_meals(lower)
        for meal_name in ("lunch", "dinner"):
            is_cancelled = meal_name in cancelled
            events.append(
                OrderEvent(
                    customer=sender,
                    date=spoken_date,
                    meal=meal_name,
                    qty=0 if is_cancelled else _meal_qty(lower, meal_name),
                    items=[] if is_cancelled else ["thali"],
                    mods=[] if is_cancelled else mods,
                    action="cancel" if is_cancelled else "new",
                    raw_text=raw_text,
                    secondary_customer=secondary_cust,
                    confidence=0.9,
                )
            )
        return events

    # Single meal or simple order
    meal_type = "dinner" if (has_dinner and not has_lunch) else "lunch"
    action = "cancel" if has_cancel else "new"

    events.append(
        OrderEvent(
            customer=sender,
            date=spoken_date,
            meal=meal_type,
            qty=0 if action == "cancel" else qty,
            items=["thali"] if action != "cancel" else [],
            mods=mods if action != "cancel" else [],
            action=action,
            raw_text=raw_text,
            secondary_customer=secondary_cust,
            confidence=0.90,
        )
    )

    return events
