"""
Gemma baseline and teacher extractor via Google AI Studio API.
Includes client-side pseudonymization, production security guardrails, retry logic, token & latency logging, and fallback resilience.
"""

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

DEFAULT_GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-2-9b-it")


class GemmaExtractor:
    """Extracts structured OrderEvent items using Gemma via Google AI Studio."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        pseudonymizer: Optional[Pseudonymizer] = None,
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or DEFAULT_GEMMA_MODEL
        self.pseudonymizer = pseudonymizer or Pseudonymizer()
        self.guardrail = InputGuardrail()

    def is_available(self) -> bool:
        """Check if a valid Google AI Studio API key is provided."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def extract_from_text(self, raw_text: str, sender: str = "Customer") -> ExtractionResult:
        """
        Extract order events from raw text.
        Passes input through production security guardrail, pseudonymizes names,
        executes API call with retries, enforces business bounds, depseudonymizes,
        and logs telemetry. Falls back gracefully if offline.
        """
        # Step 0: Adversarial Security & Input Sanitization
        audit = self.guardrail.sanitize(raw_text)
        sanitized_text = audit.clean_text

        # Step 1: Pseudonymize
        pseudo_sender, pseudo_text = self.pseudonymizer.mask_text(sender, sanitized_text)

        # Step 2: Check API key availability
        if not self.is_available():
            t0 = time.perf_counter()
            events = heuristic_extract(sanitized_text, sender)
            # Apply security flags and business bounds to fallback events
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
                model_name=f"{self.model_name}-fallback",
                latency_ms=latency,
                input_tokens=len(raw_text.split()),
                output_tokens=len(events) * 20,
                used_fallback=True,
                error="GOOGLE_API_KEY not configured: using offline heuristic fallback",
            )
            log_model_call(res)
            return res

        # Step 3: Call Google AI Studio with up to 2 retries
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            f"?key={self.api_key}"
        )

        user_content = f"Sender: {pseudo_sender}\nMessage: {pseudo_text}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_content}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        retries = 2
        last_error = None
        start_time = time.perf_counter()

        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, json=payload)
                    latency = (time.perf_counter() - start_time) * 1000

                    if resp.status_code == 200:
                        body = resp.json()
                        candidates = body.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            raw_out = parts[0].get("text", "") if parts else ""

                            usage = body.get("usageMetadata", {})
                            in_tokens = usage.get("promptTokenCount", 0)
                            out_tokens = usage.get("candidatesTokenCount", 0)

                            events, err = parse_and_validate_llm_json(
                                raw_out, raw_text=raw_text, sender=pseudo_sender
                            )

                            # Attach audit flags and enforce business bounds
                            for ev in events:
                                ev.audit_flags.extend(audit.flags)
                                if not audit.is_safe:
                                    ev.needs_review = True
                                bounded_qty, bound_flag = enforce_business_bounds(ev.qty)
                                if bound_flag:
                                    ev.qty = bounded_qty
                                    ev.audit_flags.append(bound_flag)
                                    ev.needs_review = True

                            # Depseudonymize events back to real customer names
                            real_events = [
                                self.pseudonymizer.depseudonymize_order_event(ev) for ev in events
                            ]

                            result = ExtractionResult(
                                events=real_events,
                                model_name=self.model_name,
                                latency_ms=latency,
                                input_tokens=in_tokens,
                                output_tokens=out_tokens,
                                raw_response=raw_out,
                                used_fallback=False,
                                error=err,
                            )
                            log_model_call(result)
                            return result

                    last_error = f"HTTP {resp.status_code}: {resp.text[:150]}"

            except Exception as e:
                last_error = str(e)

            time.sleep(0.5)

        # Fallback if API calls fail after retries
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
            model_name=f"{self.model_name}-fallback",
            latency_ms=latency,
            input_tokens=len(raw_text.split()),
            output_tokens=len(fallback_events) * 20,
            used_fallback=True,
            error=f"API call failed after retries: {last_error}",
        )
        log_model_call(res)
        return res
