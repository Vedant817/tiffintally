"""Hosted Gemini transport: mocked HTTP only, no key, no network.

Pins the Gemma 4 reply shapes that used to fall back to the rules without
telling anyone: a "thinking" part before the answer, a fenced answer, a model
that rejects responseMimeType, and a retired model id answering 404.
"""

import json
from datetime import datetime

import httpx
from fastapi.testclient import TestClient

from tiffintally.app import app
from tiffintally.extract.gemma import (
    DEFAULT_GEMMA_MODEL,
    GemmaExtractor,
    answer_text,
    strip_code_fences,
)
from tiffintally.parser import parse_chat_export
from tiffintally.reconcile import reconcile_ledger
from tiffintally.schema import ParsedMessage

CHAT = "17/10/2026, 8:00 pm - Asha: kal lunch 2\n17/10/2026, 8:01 pm - Ravi: kal dinner 1\n"


def _reply(payload: str, *, thought_first: str | None = None) -> httpx.Response:
    parts = []
    if thought_first is not None:
        parts.append({"text": thought_first, "thought": True})
    parts.append({"text": payload})
    return httpx.Response(
        200,
        json={"model": DEFAULT_GEMMA_MODEL, "candidates": [{"content": {"parts": parts}}]},
    )


def _events_body() -> str:
    return json.dumps(
        {
            "results": [
                {
                    "i": 0,
                    "events": [
                        {
                            "meal": "lunch",
                            "qty": 2,
                            "action": "new",
                            "mods": [],
                            "items": ["thali"],
                        }
                    ],
                },
                {"i": 1, "events": []},
            ]
        }
    )


def _gemini(monkeypatch, responder) -> GemmaExtractor:
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    extractor = GemmaExtractor(api_key="test-key-not-used", backend="gemini")
    monkeypatch.setattr(
        extractor, "endpoint", "https://example.invalid/v1beta/models/x:generateContent"
    )
    monkeypatch.setattr(extractor, "_post", responder)
    return extractor


# The Gemma 2 9B id is retired by the Gemini API and is written in parts here on
# purpose: a repo-wide grep for it must return only the line in docs/DECISIONS.md
# that explains the retirement, so no stale default or doc can hide behind a test.
RETIRED_GEMMA_2_ID = "-".join(["gemma", "2", "9b", "it"])


def test_default_model_id_is_a_gemma_4_id():
    assert DEFAULT_GEMMA_MODEL == "gemma-4-26b-a4b-it"
    assert DEFAULT_GEMMA_MODEL != RETIRED_GEMMA_2_ID


def test_answer_text_skips_thought_parts():
    body = json.loads(
        '{"candidates":[{"content":{"parts":['
        '{"text":"thinking about the order","thought":true},'
        '{"text":"{\\"results\\": []}"}]}}]}'
    )
    assert answer_text(body) == '{"results": []}'


def test_strip_code_fences():
    assert strip_code_fences('```json\n{"results": []}\n```') == '{"results": []}'
    assert strip_code_fences("```\n{}\n```") == "{}"
    assert strip_code_fences("{}") == "{}"


def test_thought_part_before_json_still_produces_model_events(monkeypatch):
    """parts[0] is a thought on Gemma 4; the JSON part behind it is the answer."""
    seen = {}

    def responder(payload):
        seen["payload"] = payload
        return _reply(_events_body(), thought_first="Let me count the plates.")

    batch = _gemini(monkeypatch, responder).extract_batch_counted(parse_chat_export(CHAT))

    assert seen["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["payload"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert batch.model_messages == 2
    assert batch.fallback_messages == 0
    assert batch.model_name == DEFAULT_GEMMA_MODEL
    assert [(ev.meal, ev.qty) for ev in batch.events] == [("lunch", 2), ("unspecified", 0)]
    # The empty row is answered, so it is flagged for review rather than dropped.
    assert batch.events[1].needs_review
    assert batch.events[1].audit_flags == ["empty_model_reply"]
    assert batch.response_mime_mode == "json"


def test_fenced_json_answer_is_parsed(monkeypatch):
    batch = _gemini(
        monkeypatch, lambda payload: _reply(f"```json\n{_events_body()}\n```")
    ).extract_batch_counted(parse_chat_export(CHAT))

    assert batch.model_messages == 2
    assert batch.fallback_messages == 0
    assert [(ev.meal, ev.qty) for ev in batch.events] == [("lunch", 2), ("unspecified", 0)]


def test_response_mime_type_rejection_retries_once_without_it(monkeypatch):
    payloads = []

    def responder(payload):
        payloads.append(payload)
        if "responseMimeType" in payload["generationConfig"]:
            return httpx.Response(400, text="responseMimeType is not supported")
        return _reply(_events_body())

    extractor = _gemini(monkeypatch, responder)
    batch = extractor.extract_batch_counted(parse_chat_export(CHAT))

    assert len(payloads) == 2
    assert "responseMimeType" in payloads[0]["generationConfig"]
    assert "responseMimeType" not in payloads[1]["generationConfig"]
    assert payloads[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert payloads[1]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert batch.model_messages == 2
    assert batch.response_mime_mode == "none"


def test_retired_model_id_shows_the_rules_label_and_the_error(monkeypatch):
    """A 404 must not read as a model answer."""
    batch = _gemini(
        monkeypatch,
        lambda payload: httpx.Response(404, text=f"models/{RETIRED_GEMMA_2_ID} is not found"),
    ).extract_batch_counted(parse_chat_export(CHAT))

    assert batch.model_messages == 0
    assert batch.fallback_messages == 2
    assert batch.model_name == "rules (regex)"
    assert any("404" in error for error in batch.errors)
    # The rules still answer, so a paste is never lost.
    assert [ev.meal for ev in batch.events] == ["lunch", "dinner"]


def test_gemini_model_version_labels_the_batch(monkeypatch):
    body = json.loads(_reply(_events_body()).text)
    del body["model"]
    body["modelVersion"] = "gemma-4-26b-a4b-it"
    batch = _gemini(
        monkeypatch, lambda payload: httpx.Response(200, json=body)
    ).extract_batch_counted(parse_chat_export(CHAT))

    assert batch.model_name == "gemma-4-26b-a4b-it"
    assert batch.model_messages > 0


def test_answered_batch_names_the_requested_model_when_the_body_omits_it(monkeypatch):
    body = json.loads(_reply(_events_body()).text)
    del body["model"]
    batch = _gemini(
        monkeypatch, lambda payload: httpx.Response(200, json=body)
    ).extract_batch_counted(parse_chat_export(CHAT))

    assert batch.model_name == DEFAULT_GEMMA_MODEL
    assert batch.model_messages > 0


def test_served_model_name_wins_over_the_requested_id(monkeypatch):
    body = json.loads(_reply(_events_body()).text)
    body["model"] = "gemma-4-31b-it"
    batch = _gemini(
        monkeypatch, lambda payload: httpx.Response(200, json=body)
    ).extract_batch_counted(parse_chat_export(CHAT))

    assert batch.model_name == "gemma-4-31b-it"


def test_empty_message_never_reaches_the_model(monkeypatch):
    def responder(payload):  # pragma: no cover - must never run
        raise AssertionError("no request expected")

    batch = _gemini(monkeypatch, responder).extract_batch_counted(
        [ParsedMessage(sender="Ravi", text="", timestamp=datetime(2026, 10, 17, 20))]
    )
    assert batch.model_messages == 0
    assert batch.events == []


def test_a_message_the_model_says_has_no_order_is_flagged_for_review(monkeypatch):
    batch = _gemini(
        monkeypatch, lambda payload: _reply(json.dumps({"results": [{"i": 0, "events": []}]}))
    ).extract_batch_counted(
        [ParsedMessage(sender="Ravi", text="no order here", timestamp=datetime(2026, 10, 17, 20))]
    )
    assert batch.model_messages == 1
    assert [ev.audit_flags for ev in batch.events] == [["empty_model_reply"]]
    assert batch.events[0].needs_review


def test_single_message_wrapper_reports_the_served_model(monkeypatch):
    result = _gemini(monkeypatch, lambda payload: _reply(_events_body())).extract_from_text(
        "kal lunch 2", "Asha"
    )
    assert result.used_fallback is False
    assert result.model_name == DEFAULT_GEMMA_MODEL
    assert isinstance(result.latency_ms, float)


def test_gemini_request_numbers_the_batch_and_a_model_note_credits_no_money(monkeypatch):
    body = json.dumps(
        {
            "results": [
                {
                    "i": 0,
                    "events": [
                        {"meal": "unspecified", "qty": 0, "action": "payment", "amount": 500}
                    ],
                }
            ]
        }
    )
    payload_seen = {}

    def responder(payload):
        payload_seen["text"] = payload["contents"][0]["parts"][0]["text"]
        return _reply(body)

    batch = _gemini(monkeypatch, responder).extract_batch_counted(parse_chat_export(CHAT))

    assert "### 0" in payload_seen["text"]
    # A model may report a payment, but only the ledger decides money.
    ledger = reconcile_ledger(batch.events)
    assert all(entry.total_paid == 0 for entry in ledger.values())
    assert isinstance(batch.latency_ms, float)


# --- the sheet must name the model that actually answered --------------------


def test_sheet_banner_names_the_model_that_answered(monkeypatch):
    """The claim post.md makes about the banner, pinned at the route level.

    The rules-only case is covered in tests/test_redteam_fixes.py. This is the
    other half: a hosted model answers, and the page names the served model
    instead of claiming the rules did the work.
    """
    served = json.loads(_reply(_events_body()).text)
    served["model"] = "gemma-4-31b-it"
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(
        GemmaExtractor, "_post", lambda self, payload: httpx.Response(200, json=served)
    )

    client = TestClient(app)
    # /process only redirects to /prep when the caller wants HTML.
    response = client.post(
        "/process",
        data={"raw_text": CHAT, "target_date": "tomorrow"},
        headers={"accept": "text/html"},
        follow_redirects=True,
    )
    text = response.text
    assert response.status_code == 200
    assert "gemma-4-31b-it" in text, "the banner must name the served model"
    assert "read all 2 message(s)" in text
    assert 'class="banner warn"' not in text
    assert "Rules (regex) only" not in text, "a model answered, so do not claim rules only"
    assert "mix both" not in text, "nothing was skipped, so nothing mixes"


def test_sheet_banner_says_rules_only_and_shows_the_error_on_a_404(monkeypatch):
    """The other half again: a retired model id must not read as a model answer."""
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(
        GemmaExtractor,
        "_post",
        lambda self, payload: httpx.Response(404, text="models/gemma is not found"),
    )

    client = TestClient(app)
    text = client.post(
        "/process",
        data={"raw_text": CHAT, "target_date": "tomorrow"},
        headers={"accept": "text/html"},
        follow_redirects=True,
    ).text
    assert "Rules (regex) only" in text
    assert 'class="banner warn"' in text, "a failed model must not look like a clean rules run"
    assert "404" in text, "the cook must be told why the model did not answer"
    # The model id may appear inside the quoted error, never as the answer.
    assert "read all" not in text and "Mixed read" not in text


def test_one_skipped_message_is_counted_in_the_banner_as_partial(monkeypatch):
    """A partial answer must be visible as partial, not as a clean model run."""
    partial = json.loads(_reply(_events_body()).text)
    partial["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(
        {"results": [{"i": 0, "events": [{"meal": "lunch", "qty": 2, "action": "new"}]}]}
    )
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(
        GemmaExtractor, "_post", lambda self, payload: httpx.Response(200, json=partial)
    )

    client = TestClient(app)
    text = client.post(
        "/process",
        data={"raw_text": CHAT, "target_date": "tomorrow"},
        headers={"accept": "text/html"},
        follow_redirects=True,
    ).text
    assert "1 read by the on-device rules" in text
    assert "mix both" in text
    assert 'class="banner warn"' in text
