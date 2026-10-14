"""
Optional extractor for a Thinking Machines Tinker sampling endpoint.

No Tinker fine-tune has been run in this repo. The Modal runs were Qwen2.5-0.5B
on Modal GPUs, and they are not served here. Without TINKER_API_KEY and an
explicit TINKER_API_BASE, this class returns the regex heuristic and labels the
result as a fallback. It does not call a made-up host.
"""

import logging
import os
import time
from typing import Optional

import httpx

from tiffintally.extract.base import (
    SYSTEM_PROMPT,
    ExtractionResult,
    heuristic_extract,
    log_model_call,
    parse_and_validate_llm_json,
)
from tiffintally.privacy import Pseudonymizer
from tiffintally.security import InputGuardrail, enforce_business_bounds

logger = logging.getLogger(__name__)

DEFAULT_TINKER_MODEL = os.getenv("TINKER_MODEL_ID", "tinker-not-configured")
# Empty unless the operator sets a real base URL. The old default host was invented.
TINKER_API_BASE = os.getenv("TINKER_API_BASE", "")


class TinkerExtractor:
    """Extracts OrderEvent items using a Tinker-served LoRA fine-tune on a small open model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        pseudonymizer: Optional[Pseudonymizer] = None,
    ):
        self.api_key = api_key or os.getenv("TINKER_API_KEY")
        self.model_id = model_id or DEFAULT_TINKER_MODEL
        self.pseudonymizer = pseudonymizer or Pseudonymizer()
        self.guardrail = InputGuardrail()

    def is_available(self) -> bool:
        base = (TINKER_API_BASE or "").strip()
        if not base or "thinkingmachines.ai" in base:
            return False
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def extract_from_text(self, raw_text: str, sender: str = "Customer") -> ExtractionResult:
        # Step 0: Security & Sanitization
        audit = self.guardrail.sanitize(raw_text)
        sanitized_text = audit.clean_text

        # Step 1: Pseudonymize
        pseudo_sender, pseudo_text = self.pseudonymizer.mask_text(sender, sanitized_text)

        # Step 2: Check API Key availability
        if not self.is_available():
            t0 = time.perf_counter()
            events = heuristic_extract(sanitized_text, sender)
            for ev in events:
                ev.audit_flags.extend(audit.flags)
                if not audit.is_safe:
                    ev.needs_review = True
                bounded_qty, bound_flag = enforce_business_bounds(ev.qty)
                if bound_flag:
                    ev.qty = bounded_qty
                    ev.audit_flags.append(bound_flag)
                    ev.needs_review = True

            latency = (time.perf_counter() - t0) * 1000
            res = ExtractionResult(
                events=events,
                model_name=f"{self.model_id}-fallback",
                latency_ms=latency,
                input_tokens=len(raw_text.split()),
                output_tokens=len(events) * 20,
                used_fallback=True,
                error="Tinker is not configured. Using the regex heuristic, not a fine-tuned model.",
            )
            log_model_call(res)
            return res

        # Step 3: Invoke Tinker API
        url = f"{TINKER_API_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": f"Sender: {pseudo_sender}\nMessage: {pseudo_text}"},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                latency = (time.perf_counter() - start_time) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    raw_content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    in_toks = usage.get("prompt_tokens", len(raw_text.split()))
                    out_toks = usage.get("completion_tokens", len(raw_content.split()))

                    events, err = parse_and_validate_llm_json(
                        raw_content, raw_text=raw_text, sender=pseudo_sender
                    )

                    for ev in events:
                        ev.audit_flags.extend(audit.flags)
                        if not audit.is_safe:
                            ev.needs_review = True
                        bounded_qty, bound_flag = enforce_business_bounds(ev.qty)
                        if bound_flag:
                            ev.qty = bounded_qty
                            ev.audit_flags.append(bound_flag)
                            ev.needs_review = True

                    real_events = [
                        self.pseudonymizer.depseudonymize_order_event(ev) for ev in events
                    ]

                    res = ExtractionResult(
                        events=real_events,
                        model_name=self.model_id,
                        latency_ms=latency,
                        input_tokens=in_toks,
                        output_tokens=out_toks,
                        raw_response=raw_content,
                        used_fallback=False,
                        error=err,
                    )
                    log_model_call(res)
                    return res

        except Exception as e:
            logger.warning(f"Tinker API request error: {e}")

        # Fallback
        latency = (time.perf_counter() - start_time) * 1000
        fallback_events = heuristic_extract(sanitized_text, sender)
        for ev in fallback_events:
            ev.audit_flags.extend(audit.flags)
            if not audit.is_safe:
                ev.needs_review = True
            bounded_qty, bound_flag = enforce_business_bounds(ev.qty)
            if bound_flag:
                ev.qty = bounded_qty
                ev.audit_flags.append(bound_flag)
                ev.needs_review = True

        res = ExtractionResult(
            events=fallback_events,
            model_name=f"{self.model_id}-fallback",
            latency_ms=latency,
            input_tokens=len(raw_text.split()),
            output_tokens=len(fallback_events) * 20,
            used_fallback=True,
            error="Tinker request failed, falling back to local extractor",
        )
        log_model_call(res)
        return res
