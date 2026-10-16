"""Regression checks for the red-team findings that were still open."""

import json
from datetime import datetime

from starlette.testclient import TestClient

from tiffintally.app import app
from tiffintally.extract.base import heuristic_extract
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.reconcile import reconcile_orders
from tiffintally.schema import OrderEvent


def test_aaj_raat_is_today_not_tomorrow():
    events = heuristic_extract("aaj raat 1 dinner", "Neha")
    assert events[0].date == "today"
    assert events[0].meal == "dinner"
    assert events[0].qty == 1


def test_kal_after_midnight_means_the_day_the_customer_meant():
    """ "kal" at 00:30 on the 13th is read as the evening of the 12th.

    So "kal" is the 13th, not the 14th. Before this the relative word was
    resolved against the raw stamp, which pushed a 00:30 order a day too far
    and hid it on the wrong sheet.
    """
    event = OrderEvent(
        customer="Neha",
        date="tomorrow",
        meal="lunch",
        qty=1,
        action="new",
        timestamp="2026-10-13 00:30:00",
        raw_text="kal lunch 1",
    )
    # Cook opens the sheet for the 13th later that morning.
    for_the_13th = reconcile_orders(
        [event], target_date="2026-10-13", as_of=datetime(2026, 10, 13, 9, 0)
    )
    assert for_the_13th.total_thalis == 1

    # It must not appear on the 14th, which is what the old rule produced.
    for_the_14th = reconcile_orders(
        [event], target_date="2026-10-14", as_of=datetime(2026, 10, 14, 9, 0)
    )
    assert for_the_14th.total_thalis == 0


def test_today_does_not_land_on_tomorrows_sheet():
    event = OrderEvent(
        customer="Neha",
        date="today",
        meal="dinner",
        qty=1,
        action="new",
        timestamp="2026-10-13 21:00:00",
        raw_text="aaj raat 1 dinner",
    )
    sheet = reconcile_orders(
        [event],
        target_date="tomorrow",
        as_of=datetime(2026, 10, 13, 21, 30),
    )
    assert sheet.total_thalis == 0


def test_process_does_not_add_phantom_standing_orders():
    client = TestClient(app)
    raw = "12/10/26, 9:14 pm - Ravi: kal lunch 2"
    resp = client.post(
        "/process", data={"raw_text": raw, "target_date": "2026-10-13", "cutoff": "22:00"}
    )
    assert resp.status_code == 200
    assert "Ravi" in resp.text
    for phantom in ("Priya", "Rahul", "Vikram", "Amit", "Sneha"):
        assert phantom not in resp.text
    assert "Standing orders added: none" in resp.text
    # Stronger than the old `assert "fallback" in resp.text`: the sheet must
    # name the rules *and* must not name any model that did not run.
    assert "Rules (regex) only" in resp.text
    assert "No model was called" in resp.text
    for claimed in ("gemma", "qwen", "llama", "mistral"):
        assert claimed not in resp.text.lower()


def test_sessions_do_not_share_customer_names():
    first = TestClient(app)
    second = TestClient(app)
    raw = "12/10/26, 9:14 pm - Ravi: kal lunch 2"
    posted = first.post(
        "/process",
        data={"raw_text": raw, "target_date": "2026-10-13", "cutoff": "22:00"},
    )
    assert "Ravi" in posted.text
    other = second.get("/prep")
    assert other.status_code == 200
    assert "Ravi" not in other.text


def test_gemma_sends_the_key_in_a_header(monkeypatch):
    """The key must never appear in a URL, on either backend."""
    import httpx

    seen = {}

    class FakeResponse:
        status_code = 500
        text = "no"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("tiffintally.extract.gemma.time.sleep", lambda *_: None)
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")

    GemmaExtractor(api_key="test-key-12345").extract_from_text("kal lunch 1", "A")
    assert "key=" not in seen["url"]
    assert "test-key-12345" not in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == "test-key-12345"


def test_no_modal_url_is_hard_coded():
    """There must be no default endpoint in the source.

    A hard-coded URL left a paid GPU endpoint reachable and unauthenticated by
    anyone who read the repo. MODAL_EXTRACTOR_URL has to come from the
    environment, and without it the backend is simply unavailable.
    """
    from tiffintally.extract import gemma as gemma_module

    assert gemma_module.DEFAULT_MODAL_URL == ""
    assert gemma_module.MODAL_EXTRACTOR_TOKEN == ""

    extractor = gemma_module.GemmaExtractor(backend="modal")
    assert extractor.is_available() is False
    assert "MODAL_EXTRACTOR_URL" in extractor.unavailable_reason()

    extractor = gemma_module.GemmaExtractor(backend="modal", endpoint="https://x.modal.run")
    assert extractor.is_available() is False
    assert "MODAL_EXTRACTOR_TOKEN" in extractor.unavailable_reason()

    both = gemma_module.GemmaExtractor(backend="modal", endpoint="https://x.modal.run", token="t")
    assert both.is_available() is True


def test_modal_backend_sends_a_bearer_token(monkeypatch):
    """The token goes in the Authorization header, never the URL."""
    import httpx

    seen = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"model": "x", "results": []}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    extractor = GemmaExtractor(
        backend="modal", endpoint="https://x.modal.run", token="secret-token"
    )
    extractor._post({"messages": []})
    assert seen["headers"]["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in seen["url"]


def test_modal_backend_sends_no_google_key(monkeypatch):
    """The Modal backend is unauthenticated, so no key is attached to it."""
    import httpx

    seen = {}

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"results": [[{"meal": "lunch", "qty": 1, "action": "new", "mods": []}]]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "modal")
    monkeypatch.setenv("GOOGLE_API_KEY", "should-not-be-sent")
    monkeypatch.setenv("MODAL_EXTRACTOR_TOKEN", "a-modal-bearer-token")

    result = GemmaExtractor(endpoint="https://example.modal.run").extract_from_text(
        "kal lunch 1", "A"
    )
    assert seen["url"].endswith(".modal.run")
    # The Google key must never travel to the Modal endpoint...
    assert "x-goog-api-key" not in seen["headers"]
    assert "should-not-be-sent" not in seen["url"]
    # ...and the Modal endpoint, which is a paid GPU box, is authenticated.
    assert seen["headers"]["Authorization"] == "Bearer a-modal-bearer-token"
    assert result.used_fallback is False


def test_synthetic_split_has_no_template_or_text_overlap():
    root = "data/synthetic"
    train = [
        json.loads(line) for line in open(f"{root}/train.jsonl", encoding="utf-8") if line.strip()
    ]
    test = [
        json.loads(line) for line in open(f"{root}/test.jsonl", encoding="utf-8") if line.strip()
    ]

    def norm(text: str) -> str:
        return " ".join(text.lower().split())

    train_text = {norm(row["raw_text"]) for row in train}
    test_text = {norm(row["raw_text"]) for row in test}
    assert train_text.isdisjoint(test_text)
    assert {row["template_id"] for row in train}.isdisjoint({row["template_id"] for row in test})

    from tiffintally.dates import relative_date_label

    for row in train + test:
        assert row["gold"]["date"] == relative_date_label(row["raw_text"])
