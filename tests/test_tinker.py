"""Tests for Tinker LoRA extractor and SFT dataset preparation."""

import json

from scripts.prepare_sft import OUTPUT_SFT, build_sft_dataset
from tiffintally.extract.tinker import TinkerExtractor


def test_tinker_extractor_fallback(monkeypatch):
    monkeypatch.delenv("TINKER_API_KEY", raising=False)
    extractor = TinkerExtractor(api_key=None)
    assert extractor.is_available() is False

    res = extractor.extract_from_text("kal lunch 2 plates", sender="Karan")
    assert len(res.events) >= 1
    assert res.used_fallback is True
    assert res.model_name.endswith("-fallback")
    assert res.events[0].qty == 2
    assert res.events[0].meal == "lunch"


def test_tinker_sft_dataset_structure():
    build_sft_dataset()
    assert OUTPUT_SFT.exists()

    with open(OUTPUT_SFT, "r", encoding="utf-8") as f:
        first_line = f.readline()
        data = json.loads(first_line)

    assert "messages" in data
    assert len(data["messages"]) == 3
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][1]["role"] == "user"
    assert data["messages"][2]["role"] == "assistant"
    # Assistant response must be valid JSON object with events list or list
    parsed_assistant = json.loads(data["messages"][2]["content"])
    events = (
        parsed_assistant.get("events", [])
        if isinstance(parsed_assistant, dict)
        else parsed_assistant
    )
    assert isinstance(events, list)
    assert len(events) >= 1
    assert "qty" in events[0]
