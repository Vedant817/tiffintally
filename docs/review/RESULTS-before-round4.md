# Results

Updated 14 Oct 2026 after a red-team review. Older exact-match tables in this file were wrong. They are not reproduced below.

## Retracted

Do not cite these:

- "100% exact match on 50 real WhatsApp messages." The file was `data/synthetic/real_benchmark_starter.jsonl`. It was generated with the synthetic set. Most of its texts also appeared in training. It has been removed.
- Exact-match numbers in `evals/modal_run_iter_1.json` through `evals/modal_run_iter_30.json`. Those runs were Qwen2.5-0.5B LoRA on Modal, not a 3B Tinker model. The split leaked, and rows containing "aaj", "today", or "tonight" were gold-labelled `tomorrow`. Those JSON files are kept as logs and marked `retracted`. `modal_run_iter_31.json` is a later run and is described below.
- `evals/runs/20261013_134313` and `20261013_135155`. The Gemma and Tinker names in those summaries scored the regex heuristic (sub-millisecond latency, identical scores).
- The edge table (about 286 ms, 8.6 MB, 100% EM). `benchmark-edge` slept and printed constants. It now refuses.
- TabPFN MAE 0.79 and "₹4,218 a month". The 0.79 figure was HistGradientBoosting on synthetic `data/kitchen_history.csv`. The rupee line was arithmetic on assumed plate counts, not a measurement. TabPFN's client licence is non-commercial, and this repo has no saved TabPFN API run.
- A first customer in Karve Nagar. That scene was written into the post before the features it praised existed. It has been deleted.

## What you can rerun

```bash
uv run pytest
uv run python scripts/gen_synthetic.py
uv run python scripts/gen_history.py
```

`scripts/gen_synthetic.py` dedupes text and holds out whole templates. `data/synthetic/split_report.json` records the sizes. Train and test share no template and no normalised message.

The app, with no API key, uses the regex extractor and says so on the prep sheet. A Gemma or Tinker score is real only when the saved run's model name does not end in `-fallback` and the key was set. No such run is stored.

There is no `data/private/real_test.jsonl` in git. A score on real cook messages does not exist yet.

## Forecast

`KitchenForecaster` fits HistGradientBoosting unless `TABPFN_API_KEY` is set and the client imports. The history file is synthetic, from `scripts/gen_history.py` with seed 42, starting 2026-07-01. Treat any MAE as a smoke test of that file.

## Modal run 31

Source file: `evals/modal_run_iter_31.json`, written by `scripts/modal_finetune.py` on 14 Oct 2026. App: https://modal.com/apps/vedantmahajan271/main/ap-3ZfLbwwIJrTAP7Aa7E9YmL

- Base model: `Qwen/Qwen2.5-3B-Instruct`, LoRA, A10G. Train loss 0.0971. Train time 365.5 seconds. 342 synthetic training rows.
- Held-out synthetic test: 50 rows, template-disjoint from train (`data/synthetic/split_report.json`, text overlap 0). Exact match 84.0% on meal, qty, action, mods, and date together. 8 failures. Match rates in the file are labelled `meal_f1` 0.98, `quantity_f1` 0.98, `action_f1` 1.0, `mods_f1` 0.9. Those four fields are correct-count divided by 50, not an F1 score.
- `json_validity_pct` is 100.0. That means every output parsed as JSON. It is not an order-accuracy figure.
- Generation latency in that file: p50 1275.44 ms, p95 1439.48 ms, on the A10G eval batch. This is not an on-device measurement.
- `edge_cases_passed` is `8/8`. Seven of those eight sentences also appear in the training file, so that line is not a held-out result.
- Real cook messages: not run. `data/private/real_test.jsonl` shares 36 of 50 texts with training.

The FastAPI app does not load this adapter. With no Gemma key it still uses the rules parser.
