"""The frozen test split must stay frozen.

A rule written to fix a failing test row, or a gold label edited after a score
was published, turns the reported accuracy into a training-set score. The red
review found exactly that: rules for strings that appear only in test.jsonl.

These tests read test.jsonl only to compute hashes. They never tune against it.
"""

import hashlib
import json
from pathlib import Path

import pytest

SPLIT_DIR = Path("data/synthetic")
TEST_PATH = SPLIT_DIR / "test.jsonl"
DEV_PATH = SPLIT_DIR / "dev.jsonl"
REPORT_PATH = SPLIT_DIR / "split_report.json"

# Recorded in split_report.json on 2026-10-15, when the split was frozen.
FROZEN_TEST_SHA256 = "1d7926f894a6cd090eb7eca632ea2c377d1eaaccf75144a775c521d31aae2796"
FROZEN_DEV_SHA256 = "289d41c5807e73fd7314064cb9a62f2a879c710b20e7a8dc8620c122f1f7092f"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_test_split_matches_its_recorded_hash():
    assert TEST_PATH.exists(), "frozen test split is missing"
    assert sha256_of(TEST_PATH) == FROZEN_TEST_SHA256, (
        "data/synthetic/test.jsonl changed. If this was deliberate, update the "
        "hash in split_report.json and say in RESULTS.md which scores are "
        "measured against the new file."
    )


def test_dev_split_matches_its_recorded_hash():
    assert DEV_PATH.exists(), "dev split is missing; rules are tuned against it"
    assert sha256_of(DEV_PATH) == FROZEN_DEV_SHA256


def test_split_report_records_both_hashes():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    frozen = report["frozen"]
    assert frozen["test_sha256"] == FROZEN_TEST_SHA256
    assert frozen["dev_sha256"] == FROZEN_DEV_SHA256


def test_no_test_text_appears_in_the_tuning_splits():
    """Template-disjointness, checked on the exact texts rather than a summary field."""

    def texts(path):
        return {
            (row.get("raw_text") or row.get("text") or "").strip().lower()
            for row in (
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }

    test_texts = texts(TEST_PATH)
    assert test_texts, "test split is empty"

    for tuning_path in (SPLIT_DIR / "train.jsonl", SPLIT_DIR / "dev.jsonl"):
        if not tuning_path.exists():
            continue
        overlap = test_texts & texts(tuning_path)
        assert not overlap, f"{overlap!r} appear in both test and {tuning_path.name}"


@pytest.mark.parametrize("name", ["test.jsonl", "dev.jsonl"])
def test_split_rows_carry_a_gold_label(name):
    rows = [
        json.loads(line)
        for line in (SPLIT_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    missing = [i for i, row in enumerate(rows) if not row.get("gold")]
    assert not missing, f"{name}: rows without a gold label at {missing}"
