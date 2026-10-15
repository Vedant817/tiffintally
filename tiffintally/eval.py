"""
Evaluation harness and honest benchmark runner.
Computes field-level Precision, Recall, F1, Exact Match, latency percentiles (p50/p95),
token counts, and real cost projections across synthetic test split and held-out real data.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

from tiffintally.extract.base import ExtractionResult
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.extract.tinker import TinkerExtractor

logger = logging.getLogger(__name__)

EVALS_DIR = Path("evals/runs")

# A row whose model_name ends in "-fallback" is the regex heuristic, whatever the
# extractor was configured as. Never print a vendor name over those numbers.
FALLBACK_SUFFIX = "-fallback"
REGEX_DISPLAY = "regex (fallback)"

# Blended list price for a hosted open-weight model, USD per million tokens.
# Only applied when a real API call ran. Override when the backend changes.
HOSTED_MODEL_USD_PER_MTOK = float(os.getenv("HOSTED_MODEL_USD_PER_MTOK", "0.20"))
GEMMA_INPUT_OUTPUT_USD_PER_MTOK = HOSTED_MODEL_USD_PER_MTOK


class MetricScore(BaseModel):
    precision: float
    recall: float
    f1: float


class ModelEvaluationReport(BaseModel):
    model_name: str
    dataset_name: str
    num_samples: int
    exact_match_accuracy: float
    meal_f1: float
    qty_f1: float
    action_f1: float
    mods_f1: float
    latency_p50_ms: float
    latency_p95_ms: float
    avg_input_tokens: float
    avg_output_tokens: float
    # None means "no token price applies", not zero. The regex makes no API call,
    # so any currency figure next to it would be invented arithmetic.
    estimated_cost_per_1k_msgs_usd: Optional[float] = None
    used_fallback: bool = False
    not_run_reason: Optional[str] = None
    timestamp: str


def compute_f1(gold_values: List[Any], pred_values: List[Any]) -> MetricScore:
    """Compute micro-averaged precision, recall, and F1."""
    tp = sum(1 for g, p in zip(gold_values, pred_values) if g == p and g not in [None, "", []])
    fp = sum(1 for g, p in zip(gold_values, pred_values) if g != p and p not in [None, "", []])
    fn = sum(1 for g, p in zip(gold_values, pred_values) if g != p and g not in [None, "", []])

    prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return MetricScore(precision=round(prec, 4), recall=round(rec, 4), f1=round(f1, 4))


def evaluate_extractor(
    extractor: Any,
    dataset_path: Path,
    dataset_name: str,
    max_samples: Optional[int] = None,
) -> ModelEvaluationReport:
    """Run extractor over labeled dataset and measure metrics."""
    samples = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    if max_samples:
        samples = samples[:max_samples]

    latencies = []
    in_tokens = []
    out_tokens = []

    gold_meals = []
    pred_meals = []
    gold_qtys = []
    pred_qtys = []
    gold_actions = []
    pred_actions = []
    exact_matches = 0
    gold_mods = []
    pred_mods = []
    fallback_rows = 0
    reported_name = getattr(extractor, "model_name", getattr(extractor, "model_id", "extractor"))

    for item in samples:
        sender = item.get("sender", "Customer")
        text = item.get("raw_text") or item.get("text") or ""
        gold = item.get("gold", {})

        t0 = time.perf_counter()
        result: ExtractionResult = extractor.extract_from_text(text, sender=sender)
        latency = (time.perf_counter() - t0) * 1000

        latencies.append(result.latency_ms if result.latency_ms > 0 else latency)
        in_tokens.append(result.input_tokens)
        out_tokens.append(result.output_tokens)
        if result.model_name:
            reported_name = result.model_name
        if result.used_fallback:
            fallback_rows += 1

        # First event prediction
        pred_ev = result.events[0] if result.events else None

        p_meal = pred_ev.meal if pred_ev else "unspecified"
        p_qty = pred_ev.qty if pred_ev else 0
        p_action = pred_ev.action if pred_ev else "none"

        g_meal = gold.get("meal", "unspecified")
        g_qty = gold.get("qty", 0)
        g_action = gold.get("action", "none")

        gold_meals.append(g_meal)
        pred_meals.append(p_meal)

        gold_qtys.append(g_qty)
        pred_qtys.append(p_qty)

        gold_actions.append(g_action)
        pred_actions.append(p_action)
        gold_mods.append(tuple(gold.get("mods") or []))
        pred_mods.append(tuple(pred_ev.mods) if pred_ev else tuple())

        # Check exact match across meal, qty, action
        if p_meal == g_meal and p_qty == g_qty and p_action == g_action:
            exact_matches += 1

    n = len(samples)
    meal_score = compute_f1(gold_meals, pred_meals)
    qty_score = compute_f1(gold_qtys, pred_qtys)
    action_score = compute_f1(gold_actions, pred_actions)
    em_acc = round(exact_matches / n, 4) if n > 0 else 0.0
    mod_hits = sum(1 for g, p in zip(gold_mods, pred_mods) if g == p)
    mods_accuracy = round(mod_hits / n, 4) if n else 0.0
    if fallback_rows and not str(reported_name).endswith(FALLBACK_SUFFIX):
        reported_name = f"{reported_name}{FALLBACK_SUFFIX}"

    p50_lat = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0
    avg_in = float(np.mean(in_tokens)) if in_tokens else 0.0
    avg_out = float(np.mean(out_tokens)) if out_tokens else 0.0

    # Cost is only meaningful for a real API call. The regex costs nothing to run,
    # so a $/1k figure beside it would be arithmetic against a token count the
    # regex never produced.
    is_fallback = str(reported_name).endswith(FALLBACK_SUFFIX)
    if is_fallback:
        cost_per_1k = None
    else:
        total_tokens_per_1k = (avg_in + avg_out) * 1000
        cost_per_1k = (total_tokens_per_1k / 1_000_000.0) * GEMMA_INPUT_OUTPUT_USD_PER_MTOK

    return ModelEvaluationReport(
        model_name=reported_name,
        dataset_name=dataset_name,
        num_samples=n,
        exact_match_accuracy=em_acc,
        meal_f1=meal_score.f1,
        qty_f1=qty_score.f1,
        action_f1=action_score.f1,
        mods_f1=mods_accuracy,
        latency_p50_ms=round(p50_lat, 2),
        latency_p95_ms=round(p95_lat, 2),
        avg_input_tokens=round(avg_in, 1),
        avg_output_tokens=round(avg_out, 1),
        estimated_cost_per_1k_msgs_usd=(round(cost_per_1k, 4) if cost_per_1k is not None else None),
        used_fallback=is_fallback,
        timestamp=datetime.now().isoformat(),
    )


def not_run_report(dataset_name: str, reason: str) -> Dict[str, Any]:
    """A row for a dataset that was not measured. Never a 0.0%."""
    return ModelEvaluationReport(
        model_name="NOT RUN",
        dataset_name=dataset_name,
        num_samples=0,
        exact_match_accuracy=0.0,
        meal_f1=0.0,
        qty_f1=0.0,
        action_f1=0.0,
        mods_f1=0.0,
        latency_p50_ms=0.0,
        latency_p95_ms=0.0,
        avg_input_tokens=0.0,
        avg_output_tokens=0.0,
        estimated_cost_per_1k_msgs_usd=None,
        not_run_reason=reason,
        timestamp=datetime.now().isoformat(),
    ).model_dump()


def run_full_evaluation_suite() -> Dict[str, Any]:
    """Run the suite and persist artifacts under evals/runs/<ts>/ only.

    Deliberately never writes RESULTS.md. RESULTS.md is hand-written from saved
    runs and cites their paths; a generated table over it is how the round-1
    "Gemma 2 | Tinker" headers ended up sitting on top of regex scores.
    """
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = EVALS_DIR / run_timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {
        "run_timestamp": run_timestamp,
        "date_ist": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "run_dir": str(run_dir).replace("\\", "/"),
        "report_path": f"{run_dir.as_posix()}/REPORT.md",
        "extractors": {},
    }

    # 1. Extractor benchmarks on the frozen synthetic test split
    syn_test_path = Path("data/synthetic/test.jsonl")
    if not syn_test_path.exists():
        from scripts.gen_synthetic import main as gen_syn

        gen_syn()

    gemma_ext = GemmaExtractor()
    tinker_ext = TinkerExtractor()

    rep_gemma_syn = evaluate_extractor(gemma_ext, syn_test_path, "synthetic_test_frozen")
    rep_tinker_syn = evaluate_extractor(tinker_ext, syn_test_path, "synthetic_test_frozen")

    results["extractors"]["gemma_synthetic"] = rep_gemma_syn.model_dump()
    results["extractors"]["tinker_synthetic"] = rep_tinker_syn.model_dump()

    # 2. Extractor benchmarks on held-out real data
    real_test_path = Path("data/private/real_test.jsonl")
    real_rows = 0
    if real_test_path.exists():
        with open(real_test_path, "r", encoding="utf-8") as f:
            real_rows = sum(1 for line in f if line.strip())

    if real_rows > 0:
        rep_gemma_real = evaluate_extractor(gemma_ext, real_test_path, "real_heldout_cook_messages")
        rep_tinker_real = evaluate_extractor(
            tinker_ext, real_test_path, "real_heldout_cook_messages"
        )
        results["extractors"]["gemma_real"] = rep_gemma_real.model_dump()
        results["extractors"]["tinker_real"] = rep_tinker_real.model_dump()
    else:
        reason = (
            "data/private/real_test.jsonl holds no labelled rows. No cook has "
            "supplied real messages yet, so there is nothing to score."
        )
        results["extractors"]["gemma_real"] = not_run_report("real_heldout_cook_messages", reason)
        results["extractors"]["tinker_real"] = not_run_report("real_heldout_cook_messages", reason)

    # Save run artifacts. Nothing outside this directory is written.
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    report_path = Path(results["report_path"])
    report_path.write_text(generate_run_report(results), encoding="utf-8")

    return results


def display_model_name(model_name: str) -> str:
    """Column header text. A `-fallback` row is the regex, whatever was configured."""
    name = str(model_name or "unknown")
    if name.endswith(FALLBACK_SUFFIX):
        return REGEX_DISPLAY
    return name


def _row(rep: Dict[str, Any]) -> Dict[str, str]:
    """One table row. NOT RUN rows stay words; they never become 0.0%."""
    header = display_model_name(rep.get("model_name", ""))
    if rep.get("not_run_reason"):
        return {
            "model": header,
            "exact": "NOT RUN",
            "meal_f1": "NOT RUN",
            "qty_f1": "NOT RUN",
            "action_f1": "NOT RUN",
            "mods_f1": "NOT RUN",
            "latency": "n/a",
            "cost": "n/a",
            "note": rep["not_run_reason"],
        }
    cost = rep.get("estimated_cost_per_1k_msgs_usd")
    return {
        "model": header,
        "exact": f"{rep['exact_match_accuracy'] * 100:.1f}%",
        "meal_f1": f"{rep['meal_f1']:.3f}",
        "qty_f1": f"{rep['qty_f1']:.3f}",
        "action_f1": f"{rep['action_f1']:.3f}",
        "mods_f1": f"{rep['mods_f1']:.3f}",
        "latency": f"{rep['latency_p50_ms']:.0f} / {rep['latency_p95_ms']:.0f} ms",
        "cost": f"${cost:.4f}" if cost is not None else "n/a",
        "note": "regex heuristic, no model call" if rep.get("used_fallback") else "model call",
    }


_TABLE_HEADER = (
    "| Model actually used | Exact match | Meal F1 | Qty F1 | Action F1 | Mods F1 "
    "| Latency p50/p95 | Cost /1k msgs | Note |\n"
    "| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | :--- |"
)


def _table(rows: List[Dict[str, str]]) -> str:
    lines = [_TABLE_HEADER]
    for r in rows:
        lines.append(
            f"| {r['model']} | {r['exact']} | {r['meal_f1']} | {r['qty_f1']} "
            f"| {r['action_f1']} | {r['mods_f1']} | {r['latency']} | {r['cost']} | {r['note']} |"
        )
    return "\n".join(lines)


def generate_run_report(run_data: Dict[str, Any]) -> str:
    """Render REPORT.md for this run only.

    Column headers come from the `model_name` each row actually reported, so a
    fallback row reads "regex (fallback)" instead of borrowing a vendor name.
    """
    ext = run_data.get("extractors", {})

    real_rows = [_row(ext[k]) for k in ("gemma_real", "tinker_real") if k in ext]
    syn_rows = [_row(ext[k]) for k in ("gemma_synthetic", "tinker_synthetic") if k in ext]

    not_run = [r for r in real_rows if r["exact"] == "NOT RUN"]

    return f"""# TiffinTally eval run {run_data.get("run_timestamp")}

Run time: {run_data.get("date_ist")}
Artifact: `{run_data.get("run_dir")}/summary.json`
Command: `uv run tiffintally eval`

This file is generated per run. It does not edit `RESULTS.md`, which is written by
hand from saved runs and cites their paths.

## How to read these tables

A column headed **{REGEX_DISPLAY}** means no model call happened for that row: the
extractor fell back to the regex heuristic, usually because no API key was set or
the call failed. Its cost is `n/a` because no tokens were billed. A row reading
`NOT RUN` means that dataset was not measured at all; it is not a 0.0% score.

## 1. Real held-out cook messages

{"No cook messages have been collected yet, so this table is empty by design." if not_run else ""}

{_table(real_rows) if real_rows else "_No real-message runs in this artifact._"}

## 2. Frozen synthetic test split

`data/synthetic/test.jsonl`. Frozen on {run_data.get("run_timestamp")}; extractor
rules and labels are never edited to move these numbers.

{_table(syn_rows) if syn_rows else "_No synthetic runs in this artifact._"}

## 3. What this run does not measure

- No forecast or plate-count prediction. It was removed from the product because it
  lost to simply cooking the confirmed orders.
- No on-device or edge latency. There is no on-device run.
- No TabPFN call. None was ever made.
"""
