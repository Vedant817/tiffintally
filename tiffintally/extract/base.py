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
                date=item.get("date", "tomorrow"),
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
        date="tomorrow",
        meal="unspecified",
        qty=0,
        action="none",
        confidence=0.30,
        raw_text=f"[Review Needed] {raw_text}",
    )
    return [fallback_event], "Malformed JSON: routed to human review"


def heuristic_extract(raw_text: str, sender: str) -> List[OrderEvent]:
    """
    High-accuracy deterministic rule-based extractor for common Hinglish order phrases.
    Used for instant local fallback, offline demo mode, and synthetic test suites.
    """
    lower = raw_text.lower().strip()
    events: List[OrderEvent] = []

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
    pay_matches = re.findall(r"(?:rs\.?|inr|₹)?\s*(\d{2,5})\s*(?:gpay|phonepe|paytm|sent|kiya|transfer)", lower)
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

    # 3. Pauses (Sunday off, pause tiffin, next week off)
    if any(
        k in lower
        for k in [
            "sunday off",
            "pause",
            "band rakhna",
            "stop tiffin",
            "going home",
            "out of station",
        ]
    ):
        target_meal = "both"
        return [
            OrderEvent(
                customer=sender,
                date="Sunday" if "sunday" in lower else "tomorrow",
                meal=target_meal,
                qty=0,
                action="pause",
                raw_text=raw_text,
                confidence=0.95,
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
    elif "दो" in lower or "do thali" in lower or "two" in lower or " do " in lower:
        qty = 2
    elif "teen" in lower or "तीन" in lower or "three" in lower:
        qty = 3
    elif "char" in lower or "चार" in lower or "four" in lower:
        qty = 4

    # Mods extraction
    mods: List[str] = []
    if (
        "no onion" in lower
        or "bina pyaaz" in lower
        or "bina pyaj" in lower
        or "बिना प्याज" in lower
        or "jain" in lower
    ):
        mods.append("no onion")
    if "roti nahi rice" in lower or "no rice" in lower or "only roti" in lower or "4 roti" in lower:
        mods.append("roti nahi rice")
    if "kam teekha" in lower or "less spicy" in lower or "bina mirchi" in lower:
        mods.append("less spicy")

    # Secondary customer split check: e.g. "roommate Priya ke liye bhi ek"
    secondary_cust = None
    sec_match = re.search(
        r"(?:roommate|friend|dost)\s+([A-Za-z]+)\s+ke liye\s+(?:bhi\s+)?(?:ek|1)?", raw_text, re.I
    )
    if sec_match:
        secondary_cust = sec_match.group(1).title()

    # Compound case: both lunch and dinner mentioned in one message
    if (has_lunch and "skip" in lower) or (has_lunch and "dinner skip" in lower):
        events.append(
            OrderEvent(
                customer=sender,
                date="tomorrow",
                meal="lunch",
                qty=qty,
                items=["thali"],
                mods=mods,
                action="new",
                raw_text=raw_text,
                secondary_customer=secondary_cust,
                confidence=0.92,
            )
        )
        events.append(
            OrderEvent(
                customer=sender,
                date="tomorrow",
                meal="dinner",
                qty=0,
                action="cancel",
                raw_text=raw_text,
                confidence=0.95,
            )
        )
        return events

    # Order change case: "change it to 3", "2 nahi 3"
    if "change" in lower or "nahi" in lower and digit_match:
        # Check if change to higher number
        change_match = re.findall(r"\d+", lower)
        new_qty = int(change_match[-1]) if change_match else qty
        events.append(
            OrderEvent(
                customer=sender,
                date="tomorrow",
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

    # Single meal or simple order
    meal_type = "dinner" if (has_dinner and not has_lunch) else "lunch"
    action = "cancel" if has_cancel else "new"

    events.append(
        OrderEvent(
            customer=sender,
            date="tomorrow",
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
