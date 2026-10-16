"""Offline-first evaluation with saved event sets and the shared scorer."""

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from pydantic import BaseModel

from tiffintally.datasets import load_dataset
from tiffintally.extract.base import SYSTEM_PROMPT, ExtractionResult, heuristic_extract
from tiffintally.scoring import score_events, summarize


class MetricScore(BaseModel):
    precision: float
    recall: float
    f1: float


def compute_f1(gold_values: List[Any], pred_values: List[Any]) -> MetricScore:
    """Compute micro-averaged precision, recall, and F1."""
    tp = sum(1 for g, p in zip(gold_values, pred_values) if g == p and g not in [None, "", []])
    fp = sum(1 for g, p in zip(gold_values, pred_values) if g != p and p not in [None, "", []])
    fn = sum(1 for g, p in zip(gold_values, pred_values) if g != p and g not in [None, "", []])

    prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return MetricScore(precision=round(prec, 4), recall=round(rec, 4), f1=round(f1, 4))


class RegexExtractor:
    def extract_from_text(self, text, sender="Customer"):
        return ExtractionResult(events=heuristic_extract(text, sender), model_name="regex")


def evaluate_extractor(
    extractor,
    dataset_path,
    dataset_name,
    max_samples=None,
    out=Path("evals/final/offline/regex"),
    system="regex",
    private=False,
):
    samples = load_dataset(Path(dataset_path), private=private)
    if max_samples:
        samples = samples[:max_samples]
    rows = []
    for sample in samples:
        started = time.perf_counter()
        result = extractor.extract_from_text(
            sample.get("raw_text") or sample["text"], sender=sample["sender"]
        )
        parsed = [event.model_dump(mode="json") for event in result.events]
        gold = sample["gold"] if isinstance(sample["gold"], list) else [sample["gold"]]
        rows.append(
            dict(
                id=sample["id"],
                template_id=sample.get("template_id", sample["id"]),
                text=sample.get("raw_text") or sample["text"],
                raw_output=result.raw_response,
                parsed=parsed,
                gold=gold,
                latency_ms=(time.perf_counter() - started) * 1000,
                system="regex" if result.used_fallback else system,
                parse_ok=not bool(result.error),
                **score_events(parsed, gold, parse_ok=not bool(result.error)),
            )
        )
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    prediction_path = out / f"{dataset_name}.jsonl"
    prediction_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    meta = dict(
        system=system,
        code_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        prompt_sha256=hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        adapter_id=None,
        adapter_sha=None,
        max_new_tokens=None,
        batch_size=1,
        dtype=None,
        decoding="deterministic rules" if system == "regex" else "declared by caller",
        n=len(rows),
        date=datetime.now(timezone.utc).isoformat(),
        source=prediction_path.as_posix(),
    )
    (out / f"{dataset_name}.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return dict(**summarize(rows), metadata=meta)


def run_full_evaluation_suite(out=Path("evals/final/offline")):
    """Always offline, regardless of configured production backend or credentials."""
    out = Path(out)
    report = dict(
        regex=evaluate_extractor(
            RegexExtractor(), Path("data/synthetic/test.jsonl"), "test", out=out / "regex"
        ),
        model="NOT RUN (needs approval)",
        cost="NOT MEASURED",
    )
    private = Path("data/private/real_test.jsonl")
    try:
        load_dataset(private, private=True)
    except (FileNotFoundError, ValueError) as exc:
        report["human_holdout"] = "NOT RUN: " + str(exc)
    else:
        # Do not automatically consume a newly supplied holdout with every CLI/CI run.
        report["human_holdout"] = "Available; explicit once-per-system evaluation required"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
