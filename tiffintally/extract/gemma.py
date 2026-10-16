"""
Open-weight extractor, hosted on Modal.

The model is served by `scripts/modal_serve.py` (see evals/modal_run_iter_31.json
for the fine-tuned checkpoint this replaces). Gemma 2 is no longer served by the
Gemini API, so the old default id made every call 404 and silently fall back to
the regex. The model id and the endpoint are both configurable, and the sheet
always says which one actually ran.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from tiffintally.extract.base import (
    SYSTEM_PROMPT,
    ExtractionResult,
    heuristic_extract,
    log_model_call,
    parse_and_validate_llm_json,
)
from tiffintally.privacy import Pseudonymizer
from tiffintally.schema import OrderEvent
from tiffintally.security import InputGuardrail, enforce_business_bounds

# Served by scripts/modal_serve.py. Recorded in docs/DECISIONS.md.
#
# The web endpoint Modal prints ends in "-api.<region>.modal.run". The app URL
# without that suffix 404s, which looks exactly like a model failure.
DEFAULT_GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_MODAL_URL = os.getenv(
    "MODAL_EXTRACTOR_URL",
    "https://vedantmahajan271--tiffintally-extract-api.us-east.modal.run",
)
GEMMA_API_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_GEMMA_MODEL}:generateContent"
)

# Which hosted model answers. "modal" is the default because that is where the
# fine-tuned checkpoint is served. "gemini" uses AI Studio. "off" forces the
# local regex, which is what the test suite runs on so no test can make a
# network call.
EXTRACTOR_BACKEND = os.getenv("EXTRACTOR_BACKEND", "modal").strip().lower()

# One request per this many messages. 200 messages at 3 sequential attempts of
# up to 15s each was 7-100 minutes for one paste, which Render's request
# timeout does not survive.
BATCH_SIZE = int(os.getenv("EXTRACT_BATCH_SIZE", "40"))
REQUEST_TIMEOUT = float(os.getenv("EXTRACT_TIMEOUT", "20"))

# Retrying these cannot help: the key is wrong, the model id is gone, or the
# path is wrong. Retrying a 429 on every message is what turned one bad key into
# a hung request.
TERMINAL_STATUSES = {400, 401, 403, 404, 422}


@dataclass
class BatchResult:
    """Extraction result plus per-message accounting.

    The sheet must never claim a model ran when some messages fell back to the
    regex, which is what a page labelled "gemma-2-9b-it" with a bad key did.
    """

    events: List[OrderEvent] = field(default_factory=list)
    model_messages: int = 0
    fallback_messages: int = 0
    model_name: str = "unknown"
    errors: List[str] = field(default_factory=list)
    # What the endpoint actually reported it is serving. The configured label is
    # only a guess until a call has answered.
    served_model: Optional[str] = None
    latency_ms: float = 0.0


class GemmaExtractor:
    """Extracts structured OrderEvent items from a hosted open-weight model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        pseudonymizer: Optional[Pseudonymizer] = None,
        endpoint: Optional[str] = None,
        api_key_header: str = "x-goog-api-key",
    ):
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or DEFAULT_GEMMA_MODEL
        self.pseudonymizer = pseudonymizer or Pseudonymizer()
        self.guardrail = InputGuardrail()
        self.backend = EXTRACTOR_BACKEND
        self.served_model: Optional[str] = None
        if endpoint:
            self.endpoint = endpoint
        elif self.backend == "gemini":
            self.endpoint = GEMMA_API_ENDPOINT
        elif self.backend == "off":
            self.endpoint = ""
        else:
            self.endpoint = DEFAULT_MODAL_URL
        self.api_key_header = api_key_header

    def is_available(self) -> bool:
        """True when this extractor has somewhere to send a message.

        This says nothing about whether a call will succeed. Use
        `BatchResult.fallback_messages` for that: a key can be present and every
        call can still 404 or 429.
        """
        if not self.endpoint:
            return False
        if "generativelanguage.googleapis.com" in self.endpoint:
            return bool(self.api_key and len(self.api_key.strip()) > 5)
        return True

    # -- internals ---------------------------------------------------------

    def _post(self, payload: dict) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        # Keys go in a header, never a URL, so they stay out of access logs.
        if self.api_key and self.endpoint.startswith("https://generativelanguage"):
            headers[self.api_key_header] = self.api_key
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            return client.post(self.endpoint, json=payload, headers=headers)

    def _is_modal_endpoint(self) -> bool:
        return "modal.run" in self.endpoint or "modal.host" in self.endpoint

    def _request_payload(self, messages: List[dict]) -> dict:
        lines = [f"Sender: {m['sender']}\nMessage: {m['text']}" for m in messages]
        if self._is_modal_endpoint():
            return {
                "model": self.model_name,
                "messages": [{"sender": m["sender"], "text": m["text"]} for m in messages],
            }
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\n" + "\n\n".join(lines)}],
                }
            ],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }

    def _parse_response(
        self, resp: httpx.Response, sent: List[dict], source: List[tuple]
    ) -> List[OrderEvent]:
        body = resp.json()
        events: List[OrderEvent] = []
        if self._is_modal_endpoint():
            rows = body.get("results") or body.get("events") or []
            for item, expected, (index, msg) in zip(rows, sent, source):
                payload = item if isinstance(item, list) else [item]
                raw = json.dumps({"events": payload}, ensure_ascii=False)
                parsed, _err = parse_and_validate_llm_json(
                    raw, raw_text=expected["raw_text"], sender=expected["sender"]
                )
                self._stamp(parsed, index, msg)
                events.extend(parsed)
            return events

        candidates = body.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        raw_out = parts[0].get("text", "") if parts else ""
        for expected, (index, msg) in zip(sent, source):
            parsed, _err = parse_and_validate_llm_json(
                raw_out, raw_text=expected["raw_text"], sender=expected["sender"]
            )
            self._stamp(parsed, index, msg)
            events.extend(parsed)
        return events

    def _fallback_for(
        self, messages: List[dict], source: List[tuple], error: str
    ) -> List[OrderEvent]:
        events: List[OrderEvent] = []
        for m, (index, msg) in zip(messages, source):
            audit = self.guardrail.sanitize(m["raw_text"])
            # real_sender, not the token: the sheet is for the cook, who needs to
            # read "Ravi", not "C001".
            produced = heuristic_extract(audit.clean_text, m["real_sender"])
            for ev in produced:
                ev.audit_flags.extend(audit.flags)
                if not audit.is_safe:
                    ev.needs_review = True
                bounded, flag = enforce_business_bounds(ev.qty)
                if flag:
                    ev.qty = bounded
                    ev.audit_flags.append(flag)
                    ev.needs_review = True
            self._stamp(produced, index, msg)
            events.extend(produced)
        res = ExtractionResult(
            events=events,
            model_name=f"{self.model_name}-fallback",
            used_fallback=True,
            error=error,
            input_tokens=sum(len(m["text"].split()) for m in messages),
        )
        log_model_call(res)
        return events

    # -- public ------------------------------------------------------------

    def extract_batch_counted(self, messages: list) -> BatchResult:
        """Extract every message, reporting how many really used the model."""
        result = BatchResult(model_name=self.model_name)
        usable = [
            (index, m)
            for index, m in enumerate(messages)
            if not getattr(m, "is_system", False)
            and not getattr(m, "is_media", False)
            and getattr(m, "text", "")
        ]
        if not usable:
            return result

        if not self.is_available():
            prepared = [self._prepare(m) for _, m in usable]
            result.events = self._fallback_for(
                prepared, usable, "no extractor endpoint or key configured"
            )
            result.fallback_messages = len(usable)
            result.model_name = f"{self.model_name}-fallback"
            return result

        for start in range(0, len(usable), BATCH_SIZE):
            chunk = usable[start : start + BATCH_SIZE]
            prepared = [self._prepare(m) for _, m in chunk]
            events, used_model, error = self._extract_chunk(prepared, chunk)
            result.events.extend(events)
            if used_model:
                result.model_messages += len(chunk)
            else:
                result.fallback_messages += len(chunk)
                if error:
                    result.errors.append(error)
                # A terminal status will fail on every chunk. Stop rather than
                # burn the request timeout once per message.
                if error and any(f"HTTP {code}" in error for code in TERMINAL_STATUSES):
                    rest = usable[start + len(chunk) :]
                    if rest:
                        prepared_rest = [self._prepare(m) for _, m in rest]
                        result.events.extend(
                            self._fallback_for(
                                prepared_rest,
                                rest,
                                f"stopped after a terminal error: {error}",
                            )
                        )
                    result.fallback_messages += len(rest)
                    break

        if result.fallback_messages:
            result.model_name = f"{self.model_name}-fallback"
        elif self.served_model:
            # Trust the endpoint over the configured label. The app defaulted to
            # gemma-4-26b-a4b-it while Modal served a Qwen adapter, and the
            # generated report named the wrong model.
            result.model_name = self.served_model
        result.served_model = self.served_model
        result.latency_ms = 0.0
        return result

    @staticmethod
    def _stamp(events: List[OrderEvent], index: int, msg) -> None:
        """Carry the export position and the timestamp onto one message's events.

        A message with no parseable stamp has no known day, so it is flagged:
        the ledger refuses to bill a row whose date it cannot resolve.
        """
        for ev in events:
            ev.line_index = index
            if getattr(msg, "timestamp_unparsed", False) or getattr(msg, "timestamp", None) is None:
                ev.timestamp = None
                ev.needs_review = True
                if "unparsed_timestamp" not in ev.audit_flags:
                    ev.audit_flags.append("unparsed_timestamp")
            else:
                ev.timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def _prepare(self, msg) -> dict:
        audit = self.guardrail.sanitize(msg.text)
        pseudo_sender, pseudo_text = self.pseudonymizer.mask_text(msg.sender, audit.clean_text)
        return {
            "sender": pseudo_sender,
            "text": pseudo_text,
            "raw_text": msg.text,
            "real_sender": msg.sender,
            "flags": audit.flags,
            "is_safe": audit.is_safe,
        }

    def _extract_chunk(self, prepared: List[dict], source: List[tuple]):
        start = time.perf_counter()
        last_error = None
        for attempt in range(3):
            try:
                resp = self._post(self._request_payload(prepared))
                if resp.status_code == 200:
                    body = resp.json()
                    events = self._parse_response(resp, prepared, source)
                    self.served_model = body.get("model") or self.served_model
                    latency = (time.perf_counter() - start) * 1000
                    for ev in events:
                        ev.audit_flags.extend(f for p in prepared for f in p["flags"])
                        if any(not p["is_safe"] for p in prepared):
                            ev.needs_review = True
                        bounded, flag = enforce_business_bounds(ev.qty)
                        if flag:
                            ev.qty = bounded
                            ev.audit_flags.append(flag)
                            ev.needs_review = True
                    events = [self.pseudonymizer.depseudonymize_order_event(ev) for ev in events]
                    log_model_call(
                        ExtractionResult(
                            events=events,
                            model_name=self.model_name,
                            latency_ms=latency,
                            input_tokens=sum(len(p["text"].split()) for p in prepared),
                        )
                    )
                    return events, True, None
                last_error = f"HTTP {resp.status_code}: {resp.text[:150]}"
                if resp.status_code in TERMINAL_STATUSES:
                    break
            except Exception as exc:  # network, timeout, bad JSON
                last_error = str(exc)
            time.sleep(0.4 * (attempt + 1))
        return (
            self._fallback_for(prepared, source, last_error or "model call failed"),
            False,
            last_error,
        )

    def extract_from_text(self, raw_text: str, sender: str = "Customer") -> ExtractionResult:
        """Single-message convenience wrapper kept for the eval harness."""

        class _Msg:
            text = raw_text
            is_system = False
            is_media = False
            is_safe = True
            flags: List[str] = []
            timestamp = None
            timestamp_unparsed = False

        msg = _Msg()
        msg.sender = sender
        batch = self.extract_batch_counted([msg])
        used_model = batch.fallback_messages == 0
        return ExtractionResult(
            events=batch.events,
            # What the endpoint reported, not the configured default. Printing
            # "gemma-4-26b-a4b-it" while Modal served a Qwen adapter is the same
            # class of error as labelling a regex score as a model's.
            model_name=batch.model_name if batch.model_name else self.model_name,
            used_fallback=not used_model,
            error=batch.errors[0] if batch.errors else None,
        )

    def extract_batch(self, messages: list) -> list[OrderEvent]:
        """Process a list of ParsedMessage objects into OrderEvents.

        Each event carries the message's position in the export as `line_index`.
        WhatsApp stamps have minute precision, so two messages can share one;
        without a position the reconciler would have to break the tie by whichever
        line happened to be processed first.
        """
        all_events: List[OrderEvent] = []
        for index, msg in enumerate(messages):
            if getattr(msg, "is_system", False) or getattr(msg, "is_media", False):
                continue
            if not getattr(msg, "text", ""):
                continue
            res = self.extract_from_text(msg.text, sender=msg.sender)
            for ev in res.events:
                ev.line_index = index
                if getattr(msg, "timestamp_unparsed", False) or msg.timestamp is None:
                    ev.timestamp = None
                    ev.needs_review = True
                    if "unparsed_timestamp" not in ev.audit_flags:
                        ev.audit_flags.append("unparsed_timestamp")
                else:
                    ev.timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                all_events.append(ev)
        return all_events
