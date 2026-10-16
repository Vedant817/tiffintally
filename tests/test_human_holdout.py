"""Freeze and one-use checks using synthetic test fixtures, never real messages."""

import hashlib
import json

import pytest

from tiffintally.datasets import reserve_holdout


def test_private_holdout_freeze_and_one_use(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    path = private / "real_test.jsonl"
    path.write_text("synthetic fixture\n", encoding="utf-8")
    report = {path.name: {"sha256": hashlib.sha256(path.read_text().encode()).hexdigest()}}
    (private / "real_test.freeze.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Private"):
        reserve_holdout(path, "regex", tmp_path / "public")
    reserve_holdout(path, "regex", private / "predictions")
    with pytest.raises(FileExistsError):
        reserve_holdout(path, "regex", private / "predictions")
    path.write_text("edited fixture\n")
    with pytest.raises(ValueError, match="freeze"):
        reserve_holdout(path, "base", private / "predictions")
