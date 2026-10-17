# Results

<!-- measured-results:start -->

The saved synthetic results describe the cleaned rules only; they establish neither model superiority nor accuracy on real cook messages.

| System | Split | Metric | Correct / n | Accuracy | Wilson interval | Source |
|---|---|---|---|---|---|---|
| regex | train | strict | 220 / 342 | 64.3% | 59.1 to 69.2 | evals/final/regex/train.jsonl |
| regex | train | lenient | 260 / 342 | 76.0% | 71.2 to 80.2 | evals/final/regex/train.jsonl |
| regex | dev2 | strict | 57 / 60 | 95.0% | 86.3 to 98.3 | evals/final/regex/dev2.jsonl |
| regex | dev2 | lenient | 57 / 60 | 95.0% | 86.3 to 98.3 | evals/final/regex/dev2.jsonl |
| regex | test | strict | 35 / 50 | 70.0% | 56.2 to 80.9 | evals/final/regex/test.jsonl |
| regex | test | lenient | 47 / 50 | 94.0% | 83.8 to 97.9 | evals/final/regex/test.jsonl |

Strict compares complete event sets on meal, quantity, action, canonical mods, payment amount and secondary customer. Lenient compares meal, quantity and action. Unknown mods are wrong. Date, items and review routing are not accuracy fields.

The legacy synthetic test has known sibling-template leakage and template-authored labels. dev2 is agent-authored development data; legacy dev is a training subset. Wilson intervals treat rows as independent and do not correct that leakage. See docs/KNOWN_LEAKS.md and the per-template comparison output.

Base, few-shot base, adapter and hosted baselines: NOT RUN (needs approval or credentials). Gemma baseline: NOT RUN (no GOOGLE_API_KEY in the environment, so there is no hosted-model run to compare against these rows). The historical adapter aggregates lack complete per-row outputs and cannot be independently rescored. Real/human-written holdout: NOT RUN (verified human provenance and labels missing). Cost: NOT MEASURED.

<!-- measured-results:end -->

Previous reported results and retractions are retained in `docs/review/RESULTS-before-round4.md` and `evals/retracted/`. They are historical logs, not current reproducible model measurements.
