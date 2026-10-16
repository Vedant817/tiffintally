"""Tests for Tinker LoRA extractor and SFT dataset preparation."""

import json

import pytest

from scripts.prepare_sft import build_sft_dataset
from tiffintally.extract.gemma import GemmaExtractor


def test_retired_tinker_backend_is_not_a_hidden_fallback():
    with pytest.raises(ValueError, match="Unsupported extractor backend"):
        GemmaExtractor(backend="tinker")


def test_tinker_sft_dataset_structure(tmp_path, monkeypatch):
    import scripts.prepare_sft as sft

    output = tmp_path / "sft.jsonl"
    monkeypatch.setattr(sft, "OUTPUT_SFT", output)
    build_sft_dataset()
    assert output.exists()

    with open(output, "r", encoding="utf-8") as f:
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
