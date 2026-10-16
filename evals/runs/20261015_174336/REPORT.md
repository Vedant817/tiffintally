# TiffinTally eval run 20261015_174336

Run time: 2026-10-15 17:43:36 IST
Artifact: `evals/runs/20261015_174336/summary.json`
Command: `uv run tiffintally eval`

This file is generated per run. It does not edit `RESULTS.md`, which is written by
hand from saved runs and cites their paths.

## How to read these tables

A column headed **regex (fallback)** means no model call happened for that row: the
extractor fell back to the regex heuristic, usually because no API key was set or
the call failed. Its cost is `n/a` because no tokens were billed. A row reading
`NOT RUN` means that dataset was not measured at all; it is not a 0.0% score.

## 1. Real held-out cook messages (collected from a cook, not generated)

No cook has supplied real messages yet, so this table is empty by design.

| Model actually used | Exact match | Meal F1 | Qty F1 | Action F1 | Mods F1 | Latency p50/p95 | Cost /1k msgs | Note |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | :--- |
| NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | n/a | n/a | data/private/real_test.jsonl has 50 labelled rows but no provenance marker of "collected_from_cook", so it is not a collected set of cook messages and is not scored as one. |
| NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | n/a | n/a | data/private/real_test.jsonl has 50 labelled rows but no provenance marker of "collected_from_cook", so it is not a collected set of cook messages and is not scored as one. |

## 2. Frozen synthetic test split

`data/synthetic/test.jsonl`. Frozen on 20261015_174336; extractor
rules and labels are never edited to move these numbers.

| Model actually used | Exact match | Meal F1 | Qty F1 | Action F1 | Mods F1 | Latency p50/p95 | Cost /1k msgs | Note |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | :--- |
| Qwen/Qwen2.5-3B-Instruct+lora-iteration_31 | 90.0% | 0.980 | 0.980 | 1.000 | 0.920 | 10421 / 12534 ms | not metered here | model call |
| regex (fallback) | 78.0% | 0.940 | 1.000 | 0.980 | 0.840 | 0 / 1 ms | not metered here | regex heuristic, no model call |

## 3. What this run does not measure

- No forecast or plate-count prediction. It was removed from the product because it
  lost to simply cooking the confirmed orders.
- No on-device or edge latency. There is no on-device run.
- No TabPFN call. None was ever made.
