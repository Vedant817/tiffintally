"""
Hosted open-weight extractor.

Backends, chosen by EXTRACTOR_BACKEND:

  gemini  the Gemini API. Apache-2.0 weights, one HTTP call, no cold start.
          This is the product default whenever GOOGLE_API_KEY is set.
  modal   the fine-tuned Qwen adapter in scripts/modal_serve.py. Opt-in only.
          Requires MODAL_EXTRACTOR_URL and MODAL_EXTRACTOR_TOKEN from the
          environment; there is deliberately no default URL, because a
          hard-coded one left a paid GPU endpoint open to anyone.
  off     the local rules only. What the test suite and CI run on.

Gemma 2 is no longer served by the Gemini API, so the old default id made every
call 404 and silently fall back to the rules while the sheet claimed a model had
answered. The label on the sheet now comes from a response or from nothing.

Licence note: the modal backend serves Qwen2.5-3B weights, which are
non-commercial (qwen-research). The gemini backend serves Gemma weights. See
docs/DECISIONS.md.
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

# Default model id for the Gemini path.
#
# There is deliberately no default URL for the Modal path. An earlier revision
# hard-coded one, which left a paid GPU endpoint reachable, unauthenticated, by
# anyone who read the repo. Both MODAL_EXTRACTOR_URL and MODAL_EXTRACTOR_TOKEN
# must come from the environment or the backend is unavailable.
DEFAULT_GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_MODAL_URL = os.getenv("MODAL_EXTRACTOR_URL", "").strip()
MODAL_EXTRACTOR_TOKEN = os.getenv("MODAL_EXTRACTOR_TOKEN", "").strip()
GEMMA_API_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_GEMMA_MODEL}:generateContent"
)

# Which hosted model answers.
#
#   modal  - the fine-tuned Qwen adapter in scripts/modal_serve.py. This is the
#            project's chosen backend: it is the model that was actually
#            fine-tuned and measured against the regex.
#   gemini - the Gemini API. Apache-2.0 weights, one HTTP call, no cold start.
#            A fallback for when the Modal endpoint is not configured.
#   off    - the local rules only. What the test suite and CI run on.
#
# Auto-selection is by what is actually configured, most-specific first:
# modal when both its URL and token are present, else gemini when a key is,
# else off. Nothing here reaches a GPU endpoint by accident: modal only arms
# itself when someone has deliberately exported both variables.
EXTRACTOR_BACKEND = os.getenv("EXTRACTOR_BACKEND", "").strip().lower()
if EXTRACTOR_BACKEND not in {"gemini", "modal", "off"}:
    if DEFAULT_MODAL_URL and MODAL_EXTRACTOR_TOKEN:
        EXTRACTOR_BACKEND = "modal"
    elif os.getenv("GOOGLE_API_KEY"):
        EXTRACTOR_BACKEND = "gemini"
    else:
        EXTRACTOR_BACKEND = "off"

# One request per this many messages. 200 messages at 3 sequential attempts of
# up to 15s each was 7-100 minutes for one paste, which Render's request
# timeout does not survive.
BATCH_SIZE = int(os.getenv("EXTRACT_BATCH_SIZE", "40"))
# A cold GPU start takes about 40 s, so a 20 s budget meant every attempt failed
# and the paste silently came back as rules.
REQUEST_TIMEOUT = float(os.getenv("EXTRACT_TIMEOUT", "30"))
MAX_ATTEMPTS = 2

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
        token: Optional[str] = None,
        backend: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or DEFAULT_GEMMA_MODEL
        self.pseudonymizer = pseudonymizer or Pseudonymizer()
        self.guardrail = InputGuardrail()
        self.backend = (backend or EXTRACTOR_BACKEND).strip().lower()
        self.served_model: Optional[str] = None
        # Re-read the environment at construction time rather than relying only
        # on the import-time constant. Reading it once at import means a token
        # exported after import is invisible, which is exactly what happens in
        # tests and is a needless trap in any embedded use.
        self.token = (
            token
            if token is not None
            else (MODAL_EXTRACTOR_TOKEN or os.getenv("MODAL_EXTRACTOR_TOKEN", "").strip())
        )

        if endpoint:
            self.endpoint = endpoint
        elif self.backend == "gemini":
            self.endpoint = GEMMA_API_ENDPOINT
        elif self.backend == "off":
            self.endpoint = ""
        else:
            self.endpoint = DEFAULT_MODAL_URL or os.getenv("MODAL_EXTRACTOR_URL", "").strip()
        self.api_key_header = api_key_header

    def unavailable_reason(self) -> Optional[str]:
        """Why this extractor cannot run, or None when it can.

        Surfaced to the cook instead of a silent fallback, so "rules only" is
        a stated fact rather than something the cook has to infer.
        """
        if self.backend == "off":
            return "EXTRACTOR_BACKEND=off, rules only"
        if self.backend == "gemini":
            if not self.endpoint:
                return "no Gemini endpoint configured"
            if not (self.api_key and len(self.api_key.strip()) > 5):
                return "GOOGLE_API_KEY is not set"
            return None
        if not self.endpoint:
            return "MODAL_EXTRACTOR_URL is not set"
        if not self.token:
            return "MODAL_EXTRACTOR_TOKEN is not set"
        return None

    def is_available(self) -> bool:
        """True when this extractor has somewhere to send a message.

        This says nothing about whether a call will succeed. Use
        `BatchResult.fallback_messages` for that: a key can be present and every
        call can still 404 or 429.
        """
        return self.unavailable_reason() is None

    # -- internals ---------------------------------------------------------

    def _post(self, payload: dict) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        # Keys and tokens go in a header, never a URL, so they stay out of
        # access logs and browser history.
        if self.api_key and "generativelanguage.googleapis.com" in self.endpoint:
            headers[self.api_key_header] = self.api_key
        if self.backend == "modal" and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            return client.post(self.endpoint, json=payload, headers=headers)

    def _is_modal_endpoint(self) -> bool:
        return "modal.run" in self.endpoint or "modal.host" in self.endpoint

    def _request_payload(self, messages: List[dict]) -> dict:
        if self._is_modal_endpoint():
            return {
                "model": self.model_name,
                "messages": [{"sender": m["sender"], "text": m["text"]} for m in messages],
            }
        # Numbered, and asked for an indexed reply.
        #
        # Asking for one flat "events" list and re-parsing it once per message
        # emitted N events for N messages: an "add" or a payment was multiplied
        # by the batch size. The reply now carries the message index, so results
        # are matched by index and never by position.
        blocks = [
            f"### {i}\nSender: {m['sender']}\nMessage: {m['text']}" for i, m in enumerate(messages)
        ]
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
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }

    def _parse_response(
        self, resp: httpx.Response, sent: List[dict], source: List[tuple]
    ) -> Tuple[Dict[int, List[OrderEvent]], List[int]]:
        """Model reply to (events keyed by message index, dropped indices).

        Missing indices are reported rather than shifted. A short reply used to
        be zipped against the messages, so when the model returned one row for
        three messages two customers vanished with no flag at all.
        """
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

        candidates = body.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        raw_out = parts[0].get("text", "") if parts else ""
        try:
            doc = json.loads(raw_out) if raw_out.strip() else {}
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
            # Out of range or repeated: ignore it rather than let one reply be
            # applied to the wrong message.
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

        reason = self.unavailable_reason()
        if reason:
            prepared = [self._prepare(m) for _, m in usable]
            result.events = self._fallback_for(prepared, usable, reason)
            result.fallback_messages = len(usable)
            result.errors.append(reason)
            return result

        for start in range(0, len(usable), BATCH_SIZE):
            chunk = usable[start : start + BATCH_SIZE]
            prepared = [self._prepare(m) for _, m in chunk]
            events, model_rows, dropped_rows, error = self._extract_chunk(prepared, chunk)
            result.events.extend(events)
            result.model_messages += len(model_rows)
            result.fallback_messages += len(dropped_rows)
            if dropped_rows:
                # A row the model skipped is a fallback row, not a model row.
                # Before this, a short reply silently lost whole customers.
                result.errors.append(
                    f"{len(dropped_rows)} of {len(chunk)} message(s) not answered by "
                    f"the model: {(error or 'row missing from the reply')[:80]}"
                )
            if not model_rows:
                # Nothing in this chunk came from the model. Stop rather than
                # burn the request timeout once per chunk.
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

        # The label comes from a response or from nothing.
        #
        # A partial run is the dangerous case: one batch answered and another
        # fell back. Naming the configured default there told the cook a model
        # read every message when it read none, which is how a banner ended up
        # claiming Gemma on a sheet produced entirely by the regex.
        if self.served_model and result.model_messages:
            result.model_name = self.served_model
        else:
            result.model_name = "rules (regex)"
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
        """Returns (events, model_message_indices, fallback_message_indices, error)."""
        start = time.perf_counter()
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = self._post(self._request_payload(prepared))
                if resp.status_code == 200:
                    body = resp.json()
                    by_index, dropped = self._parse_response(resp, prepared, source)
                    self.served_model = body.get("model") or self.served_model
                    latency = (time.perf_counter() - start) * 1000

                    events: List[OrderEvent] = []
                    for offset, (index, msg) in enumerate(source):
                        expected = prepared[offset]
                        produced = by_index.get(offset)
                        if produced is None:
                            # The model answered, but not for this message. The
                            # rules cover it rather than the customer vanishing.
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

                    events = [self.pseudonymizer.depseudonymize_order_event(ev) for ev in events]
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
                if resp.status_code in TERMINAL_STATUSES:
                    break
                if resp.status_code == 429:
                    # One backoff, then give up on the model for this paste.
                    time.sleep(1.0)
            except Exception as exc:  # network, timeout, bad JSON
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
            # What the endpoint reported, not the configured default. Printing
            # "gemma-4-26b-a4b-it" while Modal served a Qwen adapter is the same
            # class of error as labelling a regex score as a model's.
            model_name=batch.model_name if batch.model_name else self.model_name,
            used_fallback=not used_model,
            error=batch.errors[0] if batch.errors else None,
        )

    # `extract_batch` used to live here. It was never called: it wrapped
    # `extract_from_text` and then stamped every event `unparsed_timestamp`,
    # because the `_Msg` shim it built carried no timestamp. Nothing depended on
    # the result, so it only ever produced events that all went to review.
