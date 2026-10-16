# TiffinTally eval run 20261015_165558

Run time: 2026-10-15 16:55:58 IST
Artifact: `evals/runs/20261015_165558/summary.json`
Command: `uv run tiffintally eval`

This file is generated per run. It does not edit `RESULTS.md`, which is written by
hand from saved runs and cites their paths.

## How to read these tables

A column headed **regex (fallback)** means no model call happened for that row: the
extractor fell back to the regex heuristic, usually because no API key was set or
the call failed. Its cost is `n/a` because no tokens were billed. A row reading
`NOT RUN` means that dataset was not measured at all; it is not a 0.0% score.

## 1. Real held-out cook messages



| Model actually used | Exact match | Meal F1 | Qty F1 | Action F1 | Mods F1 | Latency p50/p95 | Cost /1k msgs | Note |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | :--- |
| gemma-4-26b-a4b-it | 88.0% | 0.980 | 0.900 | 0.960 | 0.880 | 8657 / 9577 ms | $0.0000 | model call |
| regex (fallback) | 76.0% | 0.860 | 0.840 | 0.820 | 0.820 | 0 / 1 ms | n/a | regex heuristic, no model call |

## 2. Frozen synthetic test split

`data/synthetic/test.jsonl`. Frozen on 20261015_165558; extractor
rules and labels are never edited to move these numbers.

| Model actually used | Exact match | Meal F1 | Qty F1 | Action F1 | Mods F1 | Latency p50/p95 | Cost /1k msgs | Note |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | :--- |
| gemma-4-26b-a4b-it | 98.0% | 0.980 | 0.980 | 1.000 | 0.920 | 8604 / 9403 ms | $0.0000 | model call |
| regex (fallback) | 94.0% | 0.940 | 1.000 | 0.980 | 0.840 | 0 / 1 ms | n/a | regex heuristic, no model call |

## 3. What this run does not measure

- No forecast or plate-count prediction. It was removed from the product because it
  lost to simply cooking the confirmed orders.
- No on-device or edge latency. There is no on-device run.
- No TabPFN call. None was ever made.
