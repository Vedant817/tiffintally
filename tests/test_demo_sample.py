"""The displayed synthetic example must survive both actual offline paths."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from scripts.modal_serve import _parse
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.reconcile import reconcile_ledger, reconcile_orders
from tiffintally.schema import ParsedMessage


@pytest.mark.parametrize("backend", ["off", "modal"])
def test_demo_lunch_seven_and_claimed_payment(backend, monkeypatch):
    rows = json.loads(Path("tiffintally/demo_sample.json").read_text(encoding="utf-8"))
    messages = [
        ParsedMessage(
            sender=row["sender"], text=row["text"], timestamp=datetime(2026, 10, 15, 20, index)
        )
        for index, row in enumerate(rows)
    ]
    extractor = GemmaExtractor(backend=backend, endpoint="https://test.modal.run", token="test")

    def post(payload):
        return httpx.Response(
            200,
            json={
                "model": "MOCK",
                "results": [_parse(json.dumps({"events": [row["gold"]]}))[0] for row in rows],
            },
        )

    monkeypatch.setattr(extractor, "_post", post)
    events = extractor.extract_batch_counted(messages).events
    sheet = reconcile_orders(events, "2026-10-16", as_of=datetime(2026, 10, 15, 21))
    assert sheet.total_lunch == 7
    assert next(label for label in sheet.packing_labels if label.customer == "Tanvi").qty == 1
    ledger = reconcile_ledger(events)
    assert ledger["vikram"].total_claimed == 1500
    assert ledger["vikram"].total_paid == 0


def test_demo_phrasing_does_not_copy_dataset_or_prompt_examples():
    from tiffintally.extract.base import SYSTEM_PROMPT

    texts = {
        json.loads(line)["raw_text"].lower()
        for split in ("train", "dev", "dev2", "test")
        for line in Path(f"data/synthetic/{split}.jsonl").read_text(encoding="utf-8").splitlines()
    }
    for row in json.loads(Path("tiffintally/demo_sample.json").read_text(encoding="utf-8")):
        assert row["text"].lower() not in texts
        assert row["text"].lower() not in SYSTEM_PROMPT.lower()
