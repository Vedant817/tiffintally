"""Approval and budget tests never contact a hosted service."""

import json

import pytest

from scripts.run_baselines import run
from tiffintally.gpu_budget import GpuBudget


def test_quoted_approval_example_does_not_authorize(tmp_path):
    path = tmp_path / "HUMAN_TODO.md"
    path.write_text("To approve use `approved: gpu calls 120`.")
    with pytest.raises(PermissionError):
        GpuBudget(path, tmp_path / "budget")


def test_budget_survives_restart_and_counts_messages(tmp_path):
    path = tmp_path / "HUMAN_TODO.md"
    path.write_text("approved: gpu calls 3\n")
    GpuBudget(path, tmp_path / "budget").reserve(2)
    GpuBudget(path, tmp_path / "budget").reserve(1)
    with pytest.raises(PermissionError, match="exhausted"):
        GpuBudget(path, tmp_path / "budget").reserve(1)


def test_offline_hybrid_is_labelled_incomplete(tmp_path):
    source = tmp_path / "sample.jsonl"
    source.write_text(
        json.dumps(
            dict(
                id="a",
                sender="Ravi",
                raw_text="kal lunch 2 ya 3 pata nahi",
                gold=dict(meal="unspecified", action="none", qty=0),
            )
        )
        + "\n"
    )
    result = run("hybrid", source, tmp_path / "out")
    assert result["metadata"]["system"] == "hybrid_offline_rules_only"
    assert result["metadata"]["llm_rows"] == 0
    assert result["metadata"]["deferred"] == 1
