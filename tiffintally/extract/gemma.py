"""Hosted extraction chosen from Modal credentials, Google key, OpenAI/Ollama, or off.

Modal is selected when its endpoint and bearer token are configured.
Google credentials select hosted Gemma (default: gemma-4-26b-a4b-it).
OpenAI credentials or local base URL select OpenAI-compatible endpoints (Ollama / vLLM / Groq).
Otherwise, local rules run. Response labels report what actually ran.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

# Default model id for the Google AI Studio path (open-weight Gemma 4 model).
# The Gemma 2 9B id this replaced is retired by the Gemini API: it answers 404,
# which is a terminal status here, so every call silently fell back to the rules.
DEFAULT_GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_MODAL_URL = os.getenv("MODAL_EXTRACTOR_URL", "").strip()
MODAL_EXTRACTOR_TOKEN = os.getenv("MODAL_EXTRACTOR_TOKEN", "").strip()
GEMMA_API_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_GEMMA_MODEL}:generateContent"
)

# OpenAI / Ollama compatible configuration
DEFAULT_OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
DEFAULT_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL_NAME", "qwen2.5:3b").strip()

# Which hosted model answers:
#   modal  - fine-tuned Qwen adapter on Modal
#   gemini - Google AI Studio Gemini API (e.g. gemma-4-26b-a4b-it)
#   openai - Any OpenAI-compatible endpoint (Ollama http://localhost:11434/v1, vLLM, Groq)
#   off    - deterministic regex rules
EXTRACTOR_BACKEND = os.getenv("EXTRACTOR_BACKEND", "").strip().lower()
if EXTRACTOR_BACKEND not in {"gemini", "modal", "openai", "off"}:
    if DEFAULT_MODAL_URL and MODAL_EXTRACTOR_TOKEN:
        EXTRACTOR_BACKEND = "modal"
    elif os.getenv("GOOGLE_API_KEY"):
        EXTRACTOR_BACKEND = "gemini"
    elif DEFAULT_OPENAI_BASE_URL or DEFAULT_OPENAI_KEY:
        EXTRACTOR_BACKEND = "openai"
    else:
        EXTRACTOR_BACKEND = "off"

BATCH_SIZE = int(os.getenv("EXTRACT_BATCH_SIZE", "40"))
REQUEST_TIMEOUT = float(os.getenv("EXTRACT_TIMEOUT", "30"))
MAX_ATTEMPTS = 2
TERMINAL_STATUSES = {400, 401, 403, 404, 422}

# A reply can arrive inside a ``` fence even when responseMimeType asked for JSON.
_JSON_FENCE = re.compile(r"\A```(?:json)?\s*|\s*```\Z", re.IGNORECASE)


def strip_code_fences(text: str) -> str:
    """Drop a leading ```json and a trailing ``` so json.loads can try the reply."""
    return _JSON_FENCE.sub("", (text or "").strip())


def answer_text(body: dict) -> str:
    """The answer parts of a Gemini reply, skipping any "thinking" part.

    Gemma 4 can answer with a reasoning part before the JSON part. Reading
    parts[0] returned the reasoning, so the batch parsed as empty and every
    message fell back to the rules.
    """
    candidates = body.get("candidates") or []
    parts: List[dict] = []
    if candidates:
        parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(
        str(part.get("text") or "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    )


@dataclass
class BatchResult:
    """Extraction result plus per-message accounting."""

    events: List[OrderEvent] = field(default_factory=list)
    model_messages: int = 0
    fallback_messages: int = 0
    model_name: str = "unknown"
    errors: List[str] = field(default_factory=list)
    served_model: Optional[str] = None
    latency_ms: float = 0.0
    response_mime_mode: Optional[str] = None


class GemmaExtractor:
    """Extracts structured OrderEvent items from a hosted or local open-weight model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        pseudonymizer: Optional[Pseudonymizer] = None,
        endpoint: Optional[str] = None,
        api_key_header: str = "x-goog-api-key",
        token: Optional[str] = None,
        backend: Optional[str] = None,
        openai_base_url: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or (
            DEFAULT_OPENAI_MODEL if backend == "openai" else DEFAULT_GEMMA_MODEL
        )
        self.pseudonymizer = pseudonymizer or Pseudonymizer()
        self.guardrail = InputGuardrail()
        self.backend = (backend or EXTRACTOR_BACKEND).strip().lower()
        if self.backend not in {"off", "modal", "gemini", "openai"}:
            raise ValueError(f"Unsupported extractor backend: {self.backend}")
        self.served_model: Optional[str] = None
        self.token = (
            token
            if token is not None
            else (MODAL_EXTRACTOR_TOKEN or os.getenv("MODAL_EXTRACTOR_TOKEN", "").strip())
        )
        self.openai_base_url = (
            openai_base_url
            if openai_base_url is not None
            else (DEFAULT_OPENAI_BASE_URL or "http://localhost:11434/v1")
        )
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

        if endpoint:
            self.endpoint = endpoint
        elif self.backend == "gemini":
            self.endpoint = GEMMA_API_ENDPOINT
        elif self.backend == "openai":
            self.endpoint = f"{self.openai_base_url.rstrip('/')}/chat/completions"
        elif self.backend == "off":
            self.endpoint = ""
        else:
            self.endpoint = DEFAULT_MODAL_URL or os.getenv("MODAL_EXTRACTOR_URL", "").strip()
        self.api_key_header = api_key_header
        # Which request mode the last Gemini call used. Recorded so a served
        # model that rejects responseMimeType is visible instead of silent.
        self.response_mime_mode: Optional[str] = "json" if self.backend == "gemini" else None

    def unavailable_reason(self) -> Optional[str]:
        """Why this extractor cannot run, or None when it can."""
        if self.backend == "off":
            return "EXTRACTOR_BACKEND=off, rules only"
        if self.backend == "gemini":
            if not self.endpoint:
                return "no Gemini endpoint configured"
            if not (self.api_key and len(self.api_key.strip()) > 5):
                return "GOOGLE_API_KEY is not set"
            return None
        if self.backend == "openai":
            if not self.endpoint:
                return "no OpenAI / Ollama endpoint configured"
            return None
        if not self.endpoint:
            return "MODAL_EXTRACTOR_URL is not set"
        if not self.token:
            return "MODAL_EXTRACTOR_TOKEN is not set"
        return None

    def is_available(self) -> bool:
        """True when this extractor has somewhere to send a message."""
        return self.unavailable_reason() is None

    # -- internals ---------------------------------------------------------

    def _post(self, payload: dict) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if self.api_key and "generativelanguage.googleapis.com" in self.endpoint:
            headers[self.api_key_header] = self.api_key
        if self.backend == "modal" and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.backend == "openai" and self.openai_key:
            headers["Authorization"] = f"Bearer {self.openai_key}"
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            return client.post(self.endpoint, json=payload, headers=headers)

    def _is_modal_endpoint(self) -> bool:
        return "modal.run" in self.endpoint or "modal.host" in self.endpoint

    def _request_payload(self, messages: List[dict], response_mime: bool = True) -> dict:
        if self._is_modal_endpoint():
            return {
                "model": self.model_name,
                "messages": [{"sender": m["sender"], "text": m["text"]} for m in messages],
            }

        blocks = [
            f"### {i}\nSender: {m['sender']}\nMessage: {m['text']}" for i, m in enumerate(messages)
        ]

        if self.backend == "openai":
            user_prompt = (
                "Answer for every message above. Reply strictly with JSON shaped as:\n"
                '{"results": [{"i": <the ### number>, "events": [ ... ]}]}\n'
                "and include one entry per message, including messages that contain no order (use an empty events list).\n\n"
                + "\n\n".join(blocks)
            )
            return {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
            }

        generation_config = {"temperature": 0}
        if response_mime:
            generation_config["responseMimeType"] = "application/json"
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"{SYSTEM_PROMPT}\n\n"
                                "Answer for every message above. Reply with JSON shaped as\n"
                                '{"results": [{"i": <the ### number>, "events": [ ... ]}]}\n'
                                "and include one entry per message, including messages that "
                                "contain no order (use an empty events list).\n\n"
                                + "\n\n".join(blocks)
                            )
                        }
                    ],
                }
            ],
            "generationConfig": generation_config,
        }

    def _parse_response(
        self, resp: httpx.Response, sent: List[dict], source: List[tuple]
    ) -> Tuple[Dict[int, List[OrderEvent]], List[int]]:
        body = resp.json()
        by_index: Dict[int, List[OrderEvent]] = {}
        count = len(sent)

        if self._is_modal_endpoint():
            rows = body.get("results") or body.get("events") or []
            for offset, item in enumerate(rows):
                if offset >= count:
                    continue
                payload = item if isinstance(item, list) else [item]
                expected = sent[offset]
                parsed, _err = parse_and_validate_llm_json(
                    json.dumps({"events": payload}, ensure_ascii=False),
                    raw_text=expected["raw_text"],
                    sender=expected["sender"],
                )
                by_index[offset] = parsed
            return by_index, [i for i in range(count) if i not in by_index]

        raw_out = ""
        if self.backend == "openai":
            choices = body.get("choices", [])
            raw_out = choices[0].get("message", {}).get("content", "") if choices else ""
        else:
            raw_out = answer_text(body)

        try:
            doc = json.loads(strip_code_fences(raw_out)) if raw_out.strip() else {}
        except Exception:
            doc = {}
        rows = doc.get("results") if isinstance(doc, dict) else None

        seen = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                index = int(row.get("i"))
            except (TypeError, ValueError):
                continue
            if not 0 <= index < count or index in seen:
                continue
            seen.add(index)
            expected = sent[index]
            parsed, _err = parse_and_validate_llm_json(
                json.dumps({"events": row.get("events") or []}, ensure_ascii=False),
                raw_text=expected["raw_text"],
                sender=expected["sender"],
            )
            by_index[index] = parsed

        return by_index, [i for i in range(count) if i not in by_index]

    def _fallback_for(
        self, messages: List[dict], source: List[tuple], error: str
    ) -> List[OrderEvent]:
        events: List[OrderEvent] = []
        for m, (index, msg) in zip(messages, source):
            audit = self.guardrail.sanitize(m["raw_text"])
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
        result = BatchResult(model_name="rules (regex)")
        usable = [
            (index, m)
            for index, m in enumerate(messages)
            if not getattr(m, "is_system", False)
            and not getattr(m, "is_media", False)
            and getattr(m, "text", "")
        ]
        if not usable:
            return result
        self.pseudonymizer.register_senders(m.sender for _, m in usable)
        for _, message in usable:
            referenced = re.findall(
                r"\b(?:roommate|friend|dost)\s+([A-Za-z]{3,})\b", message.text, re.I
            )
            self.pseudonymizer.register_senders(referenced)

        reason = self.unavailable_reason()
        if reason:
            prepared = [self._prepare(m) for _, m in usable]
            result.events = self._fallback_for(prepared, usable, reason)
            result.fallback_messages = len(usable)
            result.errors.append(reason)
            return result

        batch_start = time.perf_counter()
        for start in range(0, len(usable), BATCH_SIZE):
            chunk = usable[start : start + BATCH_SIZE]
            prepared = [self._prepare(m) for _, m in chunk]
            events, model_rows, dropped_rows, error = self._extract_chunk(prepared, chunk)
            result.events.extend(events)
            result.model_messages += len(model_rows)
            result.fallback_messages += len(dropped_rows)
            if dropped_rows:
                result.errors.append(
                    f"{len(dropped_rows)} of {len(chunk)} message(s) not answered by "
                    f"the model: {(error or 'row missing from the reply')[:80]}"
                )
            if not model_rows:
                rest = usable[start + len(chunk) :]
                if rest:
                    prepared_rest = [self._prepare(m) for _, m in rest]
                    result.events.extend(
                        self._fallback_for(
                            prepared_rest,
                            rest,
                            f"stopped after a failed chunk: {error}",
                        )
                    )
                result.fallback_messages += len(rest)
                break

        if self.served_model and result.model_messages:
            result.model_name = self.served_model
        else:
            result.model_name = "rules (regex)"
        result.served_model = self.served_model
        result.response_mime_mode = self.response_mime_mode
        result.latency_ms = (time.perf_counter() - batch_start) * 1000.0
        return result

    @staticmethod
    def _stamp(events: List[OrderEvent], index: int, msg) -> None:
        """Carry the export position and the timestamp onto one message's events."""
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
        """Returns (events, model_message_indices, fallback_message_indices, error)."""
        start = time.perf_counter()
        last_error = None
        response_mime = True
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = self._post(self._request_payload(prepared, response_mime=response_mime))
                if resp.status_code == 200:
                    body = resp.json()
                    by_index, dropped = self._parse_response(resp, prepared, source)
                    headers_dict = getattr(resp, "headers", {})
                    self.served_model = (
                        body.get("model")
                        or body.get("model_version")
                        or (
                            headers_dict.get("x-served-model")
                            if isinstance(headers_dict, dict)
                            else None
                        )
                        or self.served_model
                    )
                    latency = (time.perf_counter() - start) * 1000
                    events: List[OrderEvent] = []
                    for offset, (index, msg) in enumerate(source):
                        expected = prepared[offset]
                        produced = by_index.get(offset)
                        if produced is None:
                            produced = self._rules_events_for(expected)
                            for ev in produced:
                                ev.audit_flags.append("model_dropped_message")
                                ev.needs_review = True
                        for ev in produced:
                            ev.audit_flags.extend(expected["flags"])
                            if not expected["is_safe"]:
                                ev.needs_review = True
                            bounded, flag = enforce_business_bounds(ev.qty)
                            if flag:
                                ev.qty = bounded
                                ev.audit_flags.append(flag)
                                ev.needs_review = True
                        if any(
                            any(
                                flag.startswith(
                                    (
                                        "excessive_quantity",
                                        "invalid_order_quantity",
                                        "model_invalid",
                                    )
                                )
                                for flag in ev.audit_flags
                            )
                            for ev in produced
                        ):
                            for ev in produced:
                                ev.needs_review = True
                                ev.audit_flags.append("source_message_requires_review")
                        self._stamp(produced, index, msg)
                        for ev in produced:
                            ev.customer = msg.sender
                            if ev.secondary_customer:
                                secondary = self.pseudonymizer.depseudonymize(ev.secondary_customer)
                                if re.search(
                                    rf"(?<!\w){re.escape(secondary)}(?!\w)", msg.text, re.I
                                ):
                                    ev.secondary_customer = secondary
                                else:
                                    ev.secondary_customer = None
                                    ev.needs_review = True
                                    ev.audit_flags.append("unverified_secondary_customer")
                        events.extend(produced)

                    log_model_call(
                        ExtractionResult(
                            events=events,
                            model_name=self.served_model or self.model_name,
                            latency_ms=latency,
                            input_tokens=sum(len(p["text"].split()) for p in prepared),
                        )
                    )
                    model_rows = [i for i in range(len(source)) if i not in set(dropped)]
                    return events, model_rows, dropped, None

                last_error = f"HTTP {resp.status_code}: {resp.text[:150]}"
                if resp.status_code == 400 and response_mime and self.backend == "gemini":
                    # A served model can reject responseMimeType. Ask once
                    # without it and record which mode actually answered.
                    response_mime = False
                    self.response_mime_mode = "none"
                    continue
                if resp.status_code in TERMINAL_STATUSES:
                    break
                if resp.status_code == 429:
                    time.sleep(1.0)
            except Exception as exc:
                last_error = str(exc)
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.4 * (attempt + 1))

        fallback = self._fallback_for(prepared, source, last_error or "model call failed")
        return fallback, [], list(range(len(source))), last_error

    def _rules_events_for(self, prepared: dict) -> List[OrderEvent]:
        """The rules result for one message, used when the model skipped it."""
        audit = self.guardrail.sanitize(prepared["raw_text"])
        return heuristic_extract(audit.clean_text, prepared["real_sender"])

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
            model_name=batch.model_name if batch.model_name else self.model_name,
            used_fallback=not used_model,
            error=batch.errors[0] if batch.errors else None,
            latency_ms=batch.latency_ms,
        )
