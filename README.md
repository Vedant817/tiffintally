# TiffinTally

A home-kitchen tool that turns a pasted WhatsApp export into a prep sheet and a dues ledger.

Paste an export, select the delivery date and meal price, then review uncertain or
late messages. The ledger follows the same daily policy as the sheet. Payments
in chat remain claims until the cook confirms receipt. Opening and closing
balances can be carried between chats using CSV. Exporting separate chats remains
manual work; no WhatsApp integration or first cook session is claimed.

## Run locally

```bash
uv sync --all-extras --dev
uv run tiffintally serve
EXTRACTOR_BACKEND=off uv run tiffintally eval --out evals/final/offline
uv run python scripts/publish_results.py --check
```

The configured backend is selected from Modal endpoint credentials, a Google key,
or local rules. The UI reports what actually answered, including mixed fallback.
This round makes no hosted calls and does not establish deployment readiness.
The Qwen research adapter is non-commercial; its licence is separate from this
repository's MIT code licence. Built with Qwen when that backend is configured.

## Data and evidence

Train and legacy test are generated synthetic text with template-authored labels.
Legacy dev is contained in train. New dev2 is agent-authored synthetic development
text, not a blind human holdout. Frozen legacy files remain untouched. See
`docs/KNOWN_LEAKS.md`, `docs/POLICY.md`, and `HUMAN_TODO.md`.

## Privacy

Sheets and payment confirmations are scoped to a browser session in server memory.
The current privacy map implementation is under repair; do not rely on an anonymity
claim for real chat text. There is no authenticated cook account or encrypted
persistent ledger. Unknown personal information can reach a configured hosted
model. Raw customer exports belong only under ignored `data/private/`.

## Measured results

<!-- measured-results:start -->

The saved synthetic results describe the cleaned rules only; they establish neither model superiority nor accuracy on real cook messages.

| System | Split | Metric | Correct / n | Accuracy | Wilson interval | Source |
|---|---|---|---|---|---|---|
| regex | train | strict | 206 / 342 | 60.2% | 55.0 to 65.3 | evals/final/regex/train.jsonl |
| regex | train | lenient | 253 / 342 | 74.0% | 69.1 to 78.3 | evals/final/regex/train.jsonl |
| regex | dev2 | strict | 57 / 60 | 95.0% | 86.3 to 98.3 | evals/final/regex/dev2.jsonl |
| regex | dev2 | lenient | 57 / 60 | 95.0% | 86.3 to 98.3 | evals/final/regex/dev2.jsonl |
| regex | test | strict | 35 / 50 | 70.0% | 56.2 to 80.9 | evals/final/regex/test.jsonl |
| regex | test | lenient | 47 / 50 | 94.0% | 83.8 to 97.9 | evals/final/regex/test.jsonl |

Strict compares complete event sets on meal, quantity, action, canonical mods, payment amount and secondary customer. Lenient compares meal, quantity and action. Unknown mods are wrong. Date, items and review routing are not accuracy fields.

The legacy synthetic test has known sibling-template leakage and template-authored labels. dev2 is agent-authored development data; legacy dev is a training subset. Wilson intervals treat rows as independent and do not correct that leakage. See docs/KNOWN_LEAKS.md and the per-template comparison output.

Base, few-shot base, adapter and hosted baselines: NOT RUN (needs approval or credentials). The historical adapter aggregates lack complete per-row outputs and cannot be independently rescored. Real/human-written holdout: NOT RUN (verified human provenance and labels missing). Cost: NOT MEASURED.

<!-- measured-results:end -->
