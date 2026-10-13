"""
Tinker LoRA Fine-Tuned Model Extractor for small open-weight models (e.g. Qwen2.5-3B / Llama-3.2-3B).
Provides hosted sampling via Thinking Machines Tinker API with client pseudonymization
and robust offline evaluation fallback.
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

logger = logging.getLogger(__name__)

DEFAULT_TINKER_MODEL = os.getenv("TINKER_MODEL_ID", "qwen2.5-3b-tiffintally-lora")
TINKER_API_BASE = os.getenv("TINKER_API_BASE", "https://api.thinkingmachines.ai/v1")


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

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def extract_from_text(self, raw_text: str, sender: str = "Customer") -> ExtractionResult:
        # Step 1: Pseudonymize
        pseudo_sender, pseudo_text = self.pseudonymizer.mask_text(sender, raw_text)

        # Step 2: Check API Key availability
        if not self.is_available():
            t0 = time.perf_counter()
            events = heuristic_extract(raw_text, sender)
            latency = (time.perf_counter() - t0) * 1000
            res = ExtractionResult(
                events=events,
                model_name=f"{self.model_id}-surrogate",
                latency_ms=latency,
                input_tokens=len(raw_text.split()),
                output_tokens=len(events) * 20,
                used_fallback=True,
                error="TINKER_API_KEY not configured: using offline fine-tune surrogate",
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
        fallback_events = heuristic_extract(raw_text, sender)
        res = ExtractionResult(
            events=fallback_events,
            model_name=f"{self.model_id}-surrogate",
            latency_ms=latency,
            input_tokens=len(raw_text.split()),
            output_tokens=len(fallback_events) * 20,
            used_fallback=True,
            error="Tinker request failed, falling back to local extractor",
        )
        log_model_call(res)
        return res
