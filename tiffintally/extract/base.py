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
