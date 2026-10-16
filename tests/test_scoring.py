"""Scorer checks independent of model predictions and product date resolution."""

import json
from pathlib import Path

import pytest

from scripts.compare import compare, load
from tiffintally.datasets import load_dataset
from tiffintally.scoring import score_events, wilson


def event(**changes):
    row = dict(
        meal="lunch", qty=2, action="new", mods=[], payment_amount=None, secondary_customer=None
    )
    row.update(changes)
    return row


def test_event_sets_are_order_independent_and_mods_are_sets():
    events = [event(mods=["no onion", "less spicy"]), event(meal="dinner")]
    predicted = [events[1], dict(events[0], mods=["less spicy", "no onion", "no onion"])]
    assert score_events(predicted, events)["strict_ok"]
    assert not score_events(predicted[:1], events)["lenient_ok"]


def test_unknown_mods_and_missing_payment_or_secondary_are_wrong():
    assert not score_events(
        [event(mods=["unknown constraint"])], [event(mods=["unknown constraint"])]
    )["strict_ok"]
    for field, value in (("payment_amount", 1500), ("secondary_customer", "Tanvi")):
        assert not score_events([event()], [event(**{field: value})])["strict_ok"]


def test_invalid_output_never_earns_chitchat_credit():
    gold = [event(action="none", meal="unspecified", qty=0)]
    assert score_events([], gold, parse_ok=True)["strict_ok"]
    assert not score_events([], gold, parse_ok=False)["strict_ok"]


def test_known_wilson_interval_and_paired_exact_test():
    assert wilson(0, 0) is None
    low, high = wilson(39, 50)
    assert low == pytest.approx(0.6475845, abs=1e-5)
    assert high == pytest.approx(0.8724608, abs=1e-5)
    left = [
        dict(
            id=str(i),
            text=str(i),
            template_id=str(i // 2),
            gold=[event()],
            strict_ok=False,
            lenient_ok=False,
        )
        for i in range(6)
    ]
    right = [dict(row, strict_ok=True, lenient_ok=True) for row in left]
    result = compare(left, right)
    assert result["exact_mcnemar_p"] == 0.03125
    assert result["template_clustered_95"] == [1, 1]
    assert result["templates"] == 3


def test_frozen_predictions_rescore_bit_for_bit():
    rows = load(Path("evals/final/regex/test.jsonl"))
    assert compare(rows, rows)["delta_right_minus_left"] == 0


@pytest.mark.parametrize("provenance", [None, "collected_from_cook", {}, {"consent": False}])
def test_private_holdout_rejects_unverified_provenance(tmp_path, provenance):
    path = tmp_path / "real_test.jsonl"
    path.write_text(
        json.dumps(dict(id="a", sender="Ravi", text="hello", gold=event(), provenance=provenance)),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="provenance"):
        load_dataset(path, private=True)


def test_rules_and_dev2_remain_frozen():
    import hashlib

    for name, digest in json.loads(Path("data/synthetic/rules_frozen_v2.json").read_text()).items():
        assert hashlib.sha256(Path(name).read_text(encoding="utf-8").encode()).hexdigest() == digest
    report = json.loads(Path("data/synthetic/split_report_v2.json").read_text())
    assert (
        hashlib.sha256(
            # The first dev2 digest was captured from CRLF bytes on Windows.
            # Reproduce it cross-platform without changing the frozen digest.
            Path("data/synthetic/dev2.jsonl")
            .read_text(encoding="utf-8")
            .replace("\n", "\r\n")
            .encode()
        ).hexdigest()
        == report["dev2_sha256"]
    )
