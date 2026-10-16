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

# Recorded in split_report.json on 2026-10-15, from a Windows checkout where
# git had written CRLF line endings.
FROZEN_TEST_SHA256 = "1d7926f894a6cd090eb7eca632ea2c377d1eaaccf75144a775c521d31aae2796"
FROZEN_DEV_SHA256 = "289d41c5807e73fd7314064cb9a62f2a879c710b20e7a8dc8620c122f1f7092f"


def sha256_of(path: Path) -> str:
    """Hash the file's content, not its checkout.

    The frozen hashes were recorded on Windows, so the bytes on disk there had
    CRLF endings and the same file on Linux has LF. Hashing the raw bytes made
    the guard fail on every Linux checkout while passing locally, which is the
    worst way for a freeze check to behave.

    Normalising to CRLF reproduces the recorded digest on every platform, and
    `.gitattributes` pins `*.jsonl text eol=lf` so a fresh clone is stable too.
    Changing the content still changes the digest; only line endings do not.
    """
    text = path.read_bytes().decode("utf-8")
    canonical = text.replace("\r\n", "\n").replace("\n", "\r\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_test_split_matches_its_recorded_hash():
    assert TEST_PATH.exists(), "frozen test split is missing"
    assert sha256_of(TEST_PATH) == FROZEN_TEST_SHA256, (
        "data/synthetic/test.jsonl changed. If this was deliberate, update the "
        "hash in split_report.json and say in RESULTS.md which scores are "
        "measured against the new file."
    )


def test_hash_check_ignores_line_endings_only():
    """The freeze guard must fail on a content edit, never on a checkout style."""
    original = TEST_PATH.read_bytes().decode("utf-8")
    lf_form = original.replace("\r\n", "\n")
    crlf_digest = hashlib.sha256(
        original.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    ).hexdigest()
    lf_digest = hashlib.sha256(
        lf_form.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    ).hexdigest()
    assert crlf_digest == lf_digest == FROZEN_TEST_SHA256

    edited = hashlib.sha256(
        crlf_digest.replace("x", "y").encode("utf-8")
    ).hexdigest()  # a one-character edit still changes the digest
    assert edited != FROZEN_TEST_SHA256


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
