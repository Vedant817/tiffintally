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

The configured backend is selected from Modal endpoint credentials (a fine-tuned Qwen2.5-3B adapter),
a Google key (defaulting to the open-weight `gemma-4-26b-a4b-it` model on Google AI Studio), an OpenAI-compatible endpoint (e.g. local Ollama),
or local rules. The UI reports what actually answered, including mixed fallback.
The Qwen adapter is built on the `qwen-research` base model, which carries a non-commercial
research licence; the adapter itself is not published here and is not measured. That licence is
separate from this repository's MIT code licence. No hosted Gemma run has been measured yet, so
no model accuracy is claimed anywhere in this repository.

## Data and evidence

Train and legacy test are generated synthetic text with template-authored labels.
Legacy dev is contained in train. New dev2 is agent-authored synthetic development
text, not a blind human holdout. Frozen legacy files remain untouched. See
`docs/KNOWN_LEAKS.md`, `docs/POLICY.md`, and `HUMAN_TODO.md`.

## Privacy

By default and in demo mode (`TIFFINTALLY_DEMO_MODE=1` or `TIFFINTALLY_PERSIST=0`), sheets, reviews,
and payment confirmations live strictly in ephemeral server memory for the browser session and are
never written to disk.

Persistent storage in SQLite (`data/tiffintally.db`) is an explicit opt-in gated behind `TIFFINTALLY_PERSIST=1`.
When persistence is enabled, one `Pseudonymizer` per upload replaces, before any write:

- every sender name in the export, its first word, and any roommate named in a message (`roommate Sneha`), with sequential tokens (`C001`, `C002`, and so on);
- phone numbers in the Indian formats people type, and email addresses;
- flat, house, plot and room numbers, and the building or society name that follows the number (`flat 402 Sai Heights`);
- the stored `orders.customer`, `orders.secondary_customer` and `orders.payment_note` fields, using the same token map.

Two limits, both stated rather than glossed over. A street name with no flat or building number in front of it (`Baner Road`) is not matched, so street names can remain in the masked text. Masking is pattern based, so an address phrased in a way no pattern recognises is not removed either. Because the stored customer name is already a token, a kitchen reloading from the database sees `C001`, not a name.

`tests/test_db_persistence.py` pastes a bracketed export and then reads every table plus the WAL and shared-memory bytes, asserting that no name, phone number, email address or building name is on disk. It also asserts that a bare street name is still there, so this section cannot quietly drift into a stronger claim than the code supports.

Each paste uses an in-memory token map to mask identifiers before sending messages to any configured
hosted model. Masking covers common Indian phone formats, street addresses, and sender aliases.
However, unrecognised personal information can still leave the device if a hosted model is enabled.
Raw customer exports belong strictly under ignored local paths (`data/private/`).

## Scorer demo on /benchmarks

`/benchmarks` scores one extraction against a gold event and applies a set of hand-written
repair rules. It is a demonstration of the scorer: it needs labels, it starts from the offline
rules or an injected fake flaw, its repair rules were written for the same four sentences it
scores, and the adversarial suite does not reach the threshold. Pasting a chat never calls it,
and it is not a claim about extraction quality.

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

Base, few-shot base, adapter and hosted baselines: NOT RUN (needs approval or credentials). Gemma baseline: NOT RUN (no GOOGLE_API_KEY in the environment, so there is no hosted-model run to compare against these rows). The historical adapter aggregates lack complete per-row outputs and cannot be independently rescored. Real/human-written holdout: NOT RUN (verified human provenance and labels missing). Cost: NOT MEASURED.

<!-- measured-results:end -->
