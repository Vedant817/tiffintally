"""Documented audit cases, independently reconstructed without original probes."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from tiffintally.extract.base import heuristic_extract
from tiffintally.reconcile import reconcile_orders


@pytest.mark.parametrize(
    "text",
    [
        "kal lunch cancel mat karna",
        "kal lunch cancel nahi karna, 2 hi chahiye",
        "tomorrow lunch 2 don't cancel",
    ],
)
def test_negated_cancel_is_not_cancel(text):
    assert all(event.action != "cancel" for event in heuristic_extract(text, "Ravi"))


@pytest.mark.parametrize(
    "text",
    [
        "kal lunch 2 ya 3 pata nahi",
        "kal lunch 1.5",
        "kal lunch 0",
        "kal lunch 1000",
        "12 baje khana 3",
    ],
)
def test_uncertain_or_unread_order_reaches_review(text):
    assert any(event.needs_review for event in heuristic_extract(text, "Ravi"))


@pytest.mark.parametrize(
    "text,day",
    [
        ("parso lunch 2", "2026-10-17"),
        ("monday lunch 2", "2026-10-19"),
        ("Sunday off", "2026-10-18"),
    ],
)
def test_named_days_resolve(text, day):
    events = heuristic_extract(text, "Ravi")
    for event in events:
        event.timestamp = "2026-10-15 20:00:00"
    sheet = reconcile_orders(events, day, as_of=datetime(2026, 10, 15, 20))
    assert not sheet.other_days
    assert all(event.date != "unspecified" for event in events)


def test_meal_date_ignores_date_of_later_dietary_clause():
    events = heuristic_extract("kal lunch 1, aaj roti nahi extra rice dena please", "Priya")
    assert events[0].date == "tomorrow"


def test_devanagari_lunch():
    events = heuristic_extract("कल लंच तीन", "Ravi")
    assert events[0].meal == "lunch" and events[0].qty == 3


def test_no_silent_drops_on_development_data():
    for name in ("train", "dev2"):
        for line in Path(f"data/synthetic/{name}.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            events = heuristic_extract(row["raw_text"], row["sender"])
            if row["gold"]["action"] != "none":
                assert any(event.action != "none" or event.needs_review for event in events), row[
                    "id"
                ]


def test_canonical_phrases_have_development_evidence():
    texts = "\n".join(
        json.loads(line)["raw_text"].lower()
        for name in ("train", "dev2")
        for line in Path(f"data/synthetic/{name}.jsonl").read_text(encoding="utf-8").splitlines()
    )
    patterns = json.loads(Path("data/vocab/mod_patterns.json").read_text(encoding="utf-8"))
    for phrases in patterns.values():
        assert all(phrase in texts for phrase in phrases)
    forbidden = {"no spic", "replace curd", "extra sabzi", "kadak roti", "vadhare"}
    assert not forbidden.intersection(phrase for phrases in patterns.values() for phrase in phrases)
