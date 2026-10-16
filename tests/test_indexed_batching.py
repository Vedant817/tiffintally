"""Batched extraction must not multiply or lose events.

The Gemini path used to ask for one flat `events` list and then re-parse that
whole reply once per message, so three messages produced nine events: an "add"
or a payment was duplicated batch_size times. Nothing caught it because
identical new-orders collapse during reconciliation, so the sheet looked fine
while the ledger did not.

The fix is to number the messages and match results by index. These tests pin
that behaviour, and the failure modes that replaced the bug: a short reply must
not shift a row onto the wrong customer, and a row the model skipped must be
covered by the rules and flagged rather than vanishing.
"""

import json

import pytest

from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.parser import parse_chat_export

RAW = "\n".join(
    [
        "12/10/26, 8:00 pm - Asha: kal lunch 2",
        "12/10/26, 8:01 pm - Ravi: kal dinner 1",
        "12/10/26, 8:02 pm - Neha: kal lunch 1 plate no onion",
    ]
)


def _gemini_reply(rows: list) -> dict:
    """A Gemini-shaped response body whose text carries `rows`."""
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"results": rows}, ensure_ascii=False)}]}}
        ]
    }


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200):
        self.body = body
        self.status_code = status_code
        self.text = json.dumps(body)

    def json(self):
        return self.body


def _patch_client(monkeypatch, body: dict, calls: list | None = None):
    import tiffintally.extract.gemma as gemma_module

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            if calls is not None:
                calls.append({"url": url, "payload": json})
            return FakeResponse(body)

    monkeypatch.setattr(gemma_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(gemma_module, "EXTRACTOR_BACKEND", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "a-key-of-plausible-length")
    monkeypatch.setattr(gemma_module.time, "sleep", lambda *_: None)


@pytest.fixture
def three_messages():
    return parse_chat_export(RAW)


def test_three_messages_do_not_become_nine_events(monkeypatch, three_messages):
    """The regression the audit measured: 3 messages in, 9 events out."""
    _patch_client(
        monkeypatch,
        _gemini_reply(
            [
                {"i": 0, "events": [{"meal": "lunch", "qty": 2, "action": "new"}]},
                {"i": 1, "events": [{"meal": "dinner", "qty": 1, "action": "new"}]},
                {
                    "i": 2,
                    "events": [
                        {
                            "meal": "lunch",
                            "qty": 1,
                            "action": "new",
                            "mods": ["no onion"],
                        }
                    ],
                },
            ]
        ),
    )

    batch = GemmaExtractor().extract_batch_counted(three_messages)

    assert len(three_messages) == 3
    assert len(batch.events) == 3, "one event per message, not one per message per reply"
    assert batch.model_messages == 3
    assert batch.fallback_messages == 0
    assert sorted(ev.customer for ev in batch.events) == ["Asha", "Neha", "Ravi"]


def test_a_short_reply_does_not_shift_rows_onto_the_wrong_customer(monkeypatch, three_messages):
    """A reply for one message must not be credited to all three.

    Zipping a short reply against the messages is what silently reassigned a
    customer's order to somebody else.
    """
    _patch_client(
        monkeypatch,
        _gemini_reply([{"i": 0, "events": [{"meal": "lunch", "qty": 2, "action": "new"}]}]),
    )

    batch = GemmaExtractor().extract_batch_counted(three_messages)

    # Every message is still represented: two from the rules, one from the model.
    assert len(batch.events) == 3
    assert batch.model_messages == 1
    assert batch.fallback_messages == 2
    assert batch.errors, "a partial reply must be reported, not silent"

    # The model's row belongs to message 0 (Asha) and nobody else.
    assert sum(1 for ev in batch.events if ev.customer == "Asha") == 1


def test_a_row_the_model_skipped_is_flagged_for_review(monkeypatch, three_messages):
    """Missing index: cover it with the rules and say so."""
    _patch_client(
        monkeypatch,
        _gemini_reply(
            [
                {"i": 0, "events": [{"meal": "lunch", "qty": 2, "action": "new"}]},
                {"i": 1, "events": []},
            ]
        ),
    )

    batch = GemmaExtractor().extract_batch_counted(three_messages)

    flagged = [ev for ev in batch.events if "model_dropped_message" in ev.audit_flags]
    assert flagged, "a skipped message must carry the model_dropped_message flag"
    assert all(ev.needs_review for ev in flagged)
    assert batch.fallback_messages == 1


def test_out_of_range_and_duplicate_indices_are_ignored(monkeypatch, three_messages):
    """A hallucinated index must not overwrite a real customer's order."""
    _patch_client(
        monkeypatch,
        _gemini_reply(
            [
                {"i": 0, "events": [{"meal": "lunch", "qty": 2, "action": "new"}]},
                {"i": 99, "events": [{"meal": "dinner", "qty": 9, "action": "new"}]},
                {"i": 1, "events": [{"meal": "dinner", "qty": 7, "action": "new"}]},
                {"i": 1, "events": [{"meal": "dinner", "qty": 4, "action": "new"}]},
            ]
        ),
    )

    batch = GemmaExtractor().extract_batch_counted(three_messages)

    qtys = {(ev.customer, ev.meal): ev.qty for ev in batch.events}
    # First row for index 1 wins; the duplicate is discarded.
    assert qtys[("Ravi", "dinner")] == 7
    # Nothing was invented for the out-of-range index.
    assert all(ev.customer != "customer" for ev in batch.events)


def test_the_request_numbers_the_messages_and_asks_for_indices(monkeypatch, three_messages):
    """The prompt must carry the indices the parser matches on."""
    calls: list = []
    _patch_client(monkeypatch, _gemini_reply([]), calls)

    GemmaExtractor().extract_batch_counted(three_messages)

    sent = calls[0]["payload"]["contents"][0]["parts"][0]["text"]
    assert "### 0" in sent and "### 1" in sent and "### 2" in sent
    assert '"results"' in sent
    assert "including messages that contain no order" in sent


def test_modal_results_stay_aligned_with_their_messages(monkeypatch, three_messages):
    """The Modal endpoint returns a positional list; alignment still holds."""
    import tiffintally.extract.gemma as gemma_module

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            return FakeResponse(
                {
                    "model": "Qwen/Qwen2.5-3B-Instruct+lora-iteration_31",
                    "results": [
                        [{"meal": "lunch", "qty": 2, "action": "new"}],
                        [{"meal": "dinner", "qty": 1, "action": "new"}],
                        [
                            {
                                "meal": "lunch",
                                "qty": 1,
                                "action": "new",
                                "mods": ["no onion"],
                            }
                        ],
                    ],
                }
            )

    monkeypatch.setattr(gemma_module.httpx, "Client", FakeClient)
    extractor = GemmaExtractor(backend="modal", endpoint="https://x.modal.run", token="t")
    batch = extractor.extract_batch_counted(three_messages)

    assert len(batch.events) == 3
    assert batch.served_model == "Qwen/Qwen2.5-3B-Instruct+lora-iteration_31"
    assert batch.model_name == "Qwen/Qwen2.5-3B-Instruct+lora-iteration_31"
    qtys = {(ev.customer, ev.meal): ev.qty for ev in batch.events}
    assert qtys[("Asha", "lunch")] == 2
    assert qtys[("Ravi", "dinner")] == 1
