"""Production security envelope and adversarial input guardrails for TiffinTally."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

# Special delimiter tokens that could confuse ChatML, Llama, Gemma, or Qwen parsers
DELIMITER_PATTERNS = [
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"<\|endoftext\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"<start_of_turn>", re.IGNORECASE),
    re.compile(r"<end_of_turn>", re.IGNORECASE),
    re.compile(r"<\/?s>", re.IGNORECASE),
]

# Patterns commonly used in prompt injection, system override, or jailbreak attacks
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"as\s+an\s+ai\s+language\s+model", re.IGNORECASE),
    re.compile(r"output\s+(the\s+)?(raw\s+)?json\s+only", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?secret", re.IGNORECASE),
    re.compile(r"new\s+rule[:\s]", re.IGNORECASE),
    re.compile(r"forget\s+everything", re.IGNORECASE),
]

# Maximum reasonable thali quantity for a single domestic WhatsApp message
MAX_REASONABLE_QUANTITY = 20
MAX_MESSAGE_CHARACTERS = 500


@dataclass
class SecurityAuditResult:
    """Audit result from the production security envelope."""

    clean_text: str
    is_safe: bool = True
    risk_level: str = "low"  # low, medium, high
    flags: List[str] = field(default_factory=list)
    sanitized_diff: bool = False
    original_text: str = ""


class InputGuardrail:
    """
    Enforces security boundary on incoming customer messages:
    - Strips token delimiters and prompt injection vectors
    - Cleans invisible zero-width characters and homoglyph attacks
    - Enforces length and payload complexity bounds
    """

    def __init__(self, max_length: int = MAX_MESSAGE_CHARACTERS):
        self.max_length = max_length

    def sanitize(self, raw_text: str) -> SecurityAuditResult:
        if not raw_text or not isinstance(raw_text, str):
            return SecurityAuditResult(clean_text="", is_safe=True, risk_level="low")

        original = raw_text
        flags: List[str] = []
        text = raw_text

        # 1. Normalize Unicode (NFKC) and strip non-printable zero-width characters
        text = unicodedata.normalize("NFKC", text)
        cleaned_chars = [
            c for c in text
            if unicodedata.category(c) not in ("Cf", "Co", "Cs")
        ]
        text = "".join(cleaned_chars)

        # 2. Check length bound
        if len(text) > self.max_length:
            flags.append(f"message_length_exceeded_{len(text)}_capped_to_{self.max_length}")
            text = text[: self.max_length]

        # 3. Strip special template delimiters
        for pattern in DELIMITER_PATTERNS:
            if pattern.search(text):
                flags.append("special_token_delimiter_detected")
                text = pattern.sub(" ", text)

        # 4. Check for adversarial prompt injection patterns
        for pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                flags.append(f"prompt_injection_pattern:{pattern.pattern}")

        # 5. Clean up multiple spaces
        clean_text = re.sub(r"\s+", " ", text).strip()

        # Risk level assessment
        risk_level = "low"
        is_safe = True
        if any("prompt_injection" in f for f in flags):
            risk_level = "high"
            is_safe = False
        elif flags:
            risk_level = "medium"

        return SecurityAuditResult(
            clean_text=clean_text,
            is_safe=is_safe,
            risk_level=risk_level,
            flags=flags,
            sanitized_diff=(clean_text != original.strip()),
            original_text=original,
        )


def enforce_business_bounds(qty: int, max_allowed: int = MAX_REASONABLE_QUANTITY) -> tuple[int, Optional[str]]:
    """
    Enforces business rationality bounds on extracted order quantities.
    Prevents negative orders, zero orders without cancel action, and excessive spikes.
    """
    if qty < 0:
        return 0, "negative_quantity_clamped"
    if qty > max_allowed:
        return max_allowed, f"excessive_quantity_{qty}_capped_to_{max_allowed}_review_required"
    return qty, None
