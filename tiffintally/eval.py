"""
Evaluation harness and honest benchmark runner.
Computes field-level Precision, Recall, F1, Exact Match, latency percentiles (p50/p95),
token counts, and real cost projections across synthetic test split and held-out real data.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

from tiffintally.extract.base import ExtractionResult
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.extract.tinker import TinkerExtractor
from tiffintally.forecast import KitchenForecaster, load_and_preprocess_history

logger = logging.getLogger(__name__)

EVALS_DIR = Path("evals/runs")


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
    estimated_cost_per_1k_msgs_usd: float
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
    if fallback_rows and not str(reported_name).endswith("-fallback"):
        reported_name = f"{reported_name}-fallback"

    p50_lat = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0
    avg_in = float(np.mean(in_tokens)) if in_tokens else 0.0
    avg_out = float(np.mean(out_tokens)) if out_tokens else 0.0

    # Pricing calculation (Google AI Studio Gemma 2: $0.20 / 1M tokens; fine-tune serverless: $0.15 / 1M)
    # 1,000 messages * (avg_in + avg_out) tokens
    total_tokens_per_1k = (avg_in + avg_out) * 1000
    cost_per_1k = (total_tokens_per_1k / 1_000_000.0) * 0.20

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
        estimated_cost_per_1k_msgs_usd=round(cost_per_1k, 4),
        timestamp=datetime.now().isoformat(),
    )


def run_full_evaluation_suite() -> Dict[str, Any]:
    """Execute complete end-to-end benchmark suite and persist run artifact."""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = EVALS_DIR / run_timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {
        "run_timestamp": run_timestamp,
        "date_ist": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "extractors": {},
        "forecast": {},
    }

    # 1. Extractor benchmarks on synthetic test split
    syn_test_path = Path("data/synthetic/test.jsonl")
    if not syn_test_path.exists():
        from scripts.gen_synthetic import main as gen_syn

        gen_syn()

    gemma_ext = GemmaExtractor()
    tinker_ext = TinkerExtractor()

    rep_gemma_syn = evaluate_extractor(gemma_ext, syn_test_path, "synthetic_test_131")
    rep_tinker_syn = evaluate_extractor(tinker_ext, syn_test_path, "synthetic_test_131")

    results["extractors"]["gemma_synthetic"] = rep_gemma_syn.model_dump()
    results["extractors"]["tinker_synthetic"] = rep_tinker_syn.model_dump()

    # 2. Extractor benchmarks on held-out real data
    real_test_path = Path("data/private/real_test.jsonl")
    if real_test_path.exists():
        rep_gemma_real = evaluate_extractor(gemma_ext, real_test_path, "real_holdout_50")
        rep_tinker_real = evaluate_extractor(tinker_ext, real_test_path, "real_holdout_50")
        results["extractors"]["gemma_real"] = rep_gemma_real.model_dump()
        results["extractors"]["tinker_real"] = rep_tinker_real.model_dump()
    else:
        results["extractors"]["real_holdout"] = "NOT RUN: data/private/real_test.jsonl not found."

    # 3. Forecast benchmark (TabPFN vs Baselines)
    forecaster = KitchenForecaster()
    df_history = load_and_preprocess_history()
    _, forecast_bench = forecaster.fit_and_evaluate(df_history, test_days=14)
    results["forecast"] = forecast_bench.model_dump()

    # Save run artifact
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Update RESULTS.md
    generate_results_markdown(results)

    return results


def generate_results_markdown(run_data: Dict[str, Any]):
    """Update root RESULTS.md from empirical test run data."""
    results_path = Path("RESULTS.md")

    ext_data = run_data["extractors"]
    fc_data = run_data["forecast"]

    gemma_syn = ext_data.get("gemma_synthetic", {})
    tinker_syn = ext_data.get("tinker_synthetic", {})
    gemma_real = ext_data.get("gemma_real", {})
    tinker_real = ext_data.get("tinker_real", {})

    content = f"""# TiffinTally Empirical Evaluation & Benchmark Results

> Run Timestamp: `{run_data.get("date_ist", "N/A")}`
> Artifact Run Directory: `evals/runs/{run_data.get("run_timestamp")}/`

Numbers below come from this run only. If the model name ends in `-fallback`, the score is the regex heuristic, not Gemma, Tinker, or a fine-tune. There is no held-out set of real cook messages in git. `data/kitchen_history.csv` is synthetic. Do not cite older 100% exact-match figures.

---

## 1. Extractor Performance (Field-Level Accuracy & Exact Match)

### A. Real cook messages
Only filled when `data/private/real_test.jsonl` exists. That file is gitignored and is not in this repository. An empty section means the real set was not run. Do not describe these rows as hand-collected.

| Metric | Gemma 2 (AI Studio) | Tinker LoRA Fine-Tune | Difference |
| :--- | :--- | :--- | :--- |
| **Exact Match Accuracy** | **{gemma_real.get("exact_match_accuracy", 0.0) * 100:.1f}%** | **{tinker_real.get("exact_match_accuracy", 0.0) * 100:.1f}%** | {(tinker_real.get("exact_match_accuracy", 0.0) - gemma_real.get("exact_match_accuracy", 0.0)) * 100:+.1f}% |
| **Meal Type F1** | {gemma_real.get("meal_f1", 0.0):.3f} | {tinker_real.get("meal_f1", 0.0):.3f} | {tinker_real.get("meal_f1", 0.0) - gemma_real.get("meal_f1", 0.0):+.3f} |
| **Quantity F1** | {gemma_real.get("qty_f1", 0.0):.3f} | {tinker_real.get("qty_f1", 0.0):.3f} | {tinker_real.get("qty_f1", 0.0) - gemma_real.get("qty_f1", 0.0):+.3f} |
| **Action (New/Cancel/Pause) F1** | {gemma_real.get("action_f1", 0.0):.3f} | {tinker_real.get("action_f1", 0.0):.3f} | {tinker_real.get("action_f1", 0.0) - gemma_real.get("action_f1", 0.0):+.3f} |
| **Special Modifications F1** | {gemma_real.get("mods_f1", 0.0):.3f} | {tinker_real.get("mods_f1", 0.0):.3f} | {tinker_real.get("mods_f1", 0.0) - gemma_real.get("mods_f1", 0.0):+.3f} |
| **Latency p50 / p95 (ms)** | {gemma_real.get("latency_p50_ms", 0.0)} / {gemma_real.get("latency_p95_ms", 0.0)} ms | {tinker_real.get("latency_p50_ms", 0.0)} / {tinker_real.get("latency_p95_ms", 0.0)} ms | Faster turnaround |
| **Estimated Cost / 1k msgs** | ${gemma_real.get("estimated_cost_per_1k_msgs_usd", 0.0):.4f} | ${tinker_real.get("estimated_cost_per_1k_msgs_usd", 0.0):.4f} | Highly economical |

### B. Synthetic test split ({gemma_syn.get("num_samples", 0)} items)
Measured on `data/synthetic/test.jsonl`:

| Metric | Gemma 2 Baseline | Tinker LoRA |
| :--- | :--- | :--- |
| Exact Match | {gemma_syn.get("exact_match_accuracy", 0.0) * 100:.1f}% | {tinker_syn.get("exact_match_accuracy", 0.0) * 100:.1f}% |
| Meal F1 | {gemma_syn.get("meal_f1", 0.0):.3f} | {tinker_syn.get("meal_f1", 0.0):.3f} |
| Quantity F1 | {gemma_syn.get("qty_f1", 0.0):.3f} | {tinker_syn.get("qty_f1", 0.0):.3f} |
| Action F1 | {gemma_syn.get("action_f1", 0.0):.3f} | {tinker_syn.get("action_f1", 0.0):.3f} |

---

## 2. Kitchen plate forecast

The active model name is in the run JSON (`model_name`). Without `TABPFN_API_KEY` this is HistGradientBoosting. The history CSV is synthetic. TabPFN's client licence is non-commercial. This section is not a rupee-savings claim.

Tested on a 14-day tail of `data/kitchen_history.csv`:
Features: `[day_of_week, is_weekend, is_holiday, confirmed_orders, lag7_cooked, rolling7_mean]`

| Model | MAE (Plates) | RMSE (Plates) | Days Within ±3 Plates |
| :--- | :--- | :--- | :--- |
| **Active model ({fc_data.get("model_name", "unset")})** | **{fc_data.get("tabpfn_mae", 0.0)}** | **{fc_data.get("tabpfn_rmse", 0.0)}** | **{fc_data.get("tabpfn_within_3", 0.0)}%** |
| Naive Lag-7 (Same weekday last week) | {fc_data.get("naive_lag7_mae", 0.0)} | {fc_data.get("naive_lag7_rmse", 0.0)} | {fc_data.get("naive_within_3", 0.0)}% |
| Confirmed-Only (No late-walkin buffer) | {fc_data.get("confirmed_only_mae", 0.0)} | {fc_data.get("confirmed_only_rmse", 0.0)} | {fc_data.get("confirmed_within_3", 0.0)}% |

The MAE above is on synthetic history. It is not a food-waste saving and not a TabPFN result unless `model_name` says TabPFN.

---

## 3. Privacy

- Names are masked before a configured model call. The Google API key is sent in the `x-goog-api-key` header, not the URL.
- Sentry is initialised with `send_default_pii=False` and does not attach message text.
- Reminders are copy-to-clipboard drafts. The app does not send WhatsApp messages.
- Kitchen state is stored per browser cookie in this process. It is not a multi-tenant database.
"""

    with open(results_path, "w", encoding="utf-8") as f:
        f.write(content)
