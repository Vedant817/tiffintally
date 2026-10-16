"""Session maps and outbound masking at the real client boundary."""

import json
from datetime import datetime

import httpx

from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.privacy import Pseudonymizer
from tiffintally.schema import ParsedMessage


def test_default_maps_are_isolated_and_do_not_create_sqlite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first, second = Pseudonymizer(), Pseudonymizer()
    token = first.get_or_create_pseudo_id("Private Cook")
    assert second.depseudonymize(token) == token
    assert not list(tmp_path.rglob("*.db"))


def test_future_sender_and_roommate_are_masked_before_first_batch(monkeypatch):
    extractor = GemmaExtractor(backend="modal", endpoint="https://test.modal.run", token="test")
    messages = [
        ParsedMessage(
            sender="Ravi",
            text="kal lunch 2 roommate Tanvi ke liye ek; LaterName will collect",
            timestamp=datetime(2026, 10, 15, 20),
        )
    ]
    messages += [
        ParsedMessage(sender="Other", text="hello", timestamp=datetime(2026, 10, 15, 20))
        for _ in range(41)
    ]
    messages += [
        ParsedMessage(sender="LaterName", text="hello", timestamp=datetime(2026, 10, 15, 20))
    ]
    observed = []

    def post(payload):
        observed.append(json.dumps(payload))
        return httpx.Response(
            200,
            json={
                "model": "MOCK",
                "results": [
                    [dict(customer="C999", meal="lunch", action="new", qty=1, date="tomorrow")]
                    for _ in payload["messages"]
                ],
            },
        )

    monkeypatch.setattr(extractor, "_post", post)
    extractor.extract_batch_counted(messages)
    assert observed
    for name in ("Ravi", "Tanvi", "LaterName"):
        assert name not in observed[0]


def test_real_display_name_that_looks_like_token_is_not_resolved_again(monkeypatch):
    extractor = GemmaExtractor(backend="modal", endpoint="https://test.modal.run", token="test")
    monkeypatch.setattr(
        extractor,
        "_post",
        lambda payload: httpx.Response(
            200,
            json={
                "results": [
                    [dict(customer="C999", date="tomorrow", meal="lunch", qty=1, action="new")]
                    for _ in payload["messages"]
                ]
            },
        ),
    )
    messages = [
        ParsedMessage(sender=name, text="kal lunch 1", timestamp=datetime(2026, 10, 15, 20))
        for name in ("Asha", "C001")
    ]
    assert [event.customer for event in extractor.extract_batch_counted(messages).events] == [
        "Asha",
        "C001",
    ]


def test_spaced_phone_and_complete_address_are_removed():
    _, masked = Pseudonymizer().mask_text("Ravi", "call +91 9 8 7 6 5 4 3 2 1 0 at flat 402")
    assert "402" not in masked and "7 6 5" not in masked


def test_name_normalization_matches_guardrail_before_outbound_masking():
    for name in ("Ａｓｈａ", "A\u200bsha"):
        extractor = GemmaExtractor(backend="off")
        prepared = extractor._prepare(
            ParsedMessage(
                sender=name, text=name + " kal lunch 1", timestamp=datetime(2026, 10, 15, 20)
            )
        )
        assert "Asha" not in prepared["text"]
        assert extractor.pseudonymizer.depseudonymize(prepared["sender"]) == name
