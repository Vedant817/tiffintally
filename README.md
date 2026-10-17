# TiffinTally

A home-kitchen tool that turns a pasted WhatsApp export into a prep sheet and a dues ledger.

Paste an export, select the delivery date and meal price, then review uncertain or
late messages. The ledger follows the same daily policy as the sheet. Payments
in chat remain claims until the cook confirms receipt. Opening and closing
balances can be carried between chats using CSV. Exporting separate chats remains
manual work; no WhatsApp integration or first cook session is claimed.

## Try it

**Live:** <https://tiffintally-lbn2.onrender.com>

The deployed instance runs in demo mode: sheets, reviews and payment confirmations stay
in memory for your browser session and are never written to disk, so anything you paste
into it is discarded when you close the tab. No model key is configured there, so it
answers with the local rules path and says so in the UI rather than pretending a hosted
model replied.

## Stack

Python 3.11 · FastAPI · Jinja2 templates · SQLite (opt-in) · pytest · Hypothesis · ruff ·
Render (hosting) · GitHub Actions (CI and pull-request previews).

## Run locally

```bash
uv sync --all-extras --dev
uv run tiffintally serve
EXTRACTOR_BACKEND=off uv run tiffintally eval --out evals/final/offline
uv run python scripts/publish_results.py --check
```

`tiffintally eval` regenerates the frozen **test** split only. Train, dev2 and test
together are `EXTRACTOR_BACKEND=off uv run python scripts/regex_report.py`.

The configured backend is selected from Modal endpoint credentials (a fine-tuned Qwen2.5-3B adapter),
a Google key (defaulting to the open-weight `gemma-4-26b-a4b-it` model on Google AI Studio), an OpenAI-compatible endpoint (e.g. local Ollama),
or local rules. The UI reports what actually answered, including mixed fallback.
The Qwen adapter is built on the `qwen-research` base model, which carries a non-commercial
research licence; the adapter itself is not published here and is not measured. That licence is
separate from this repository's MIT code licence. No hosted Gemma run has been measured yet, so
no model accuracy is claimed anywhere in this repository.

## Automated testing

Every pull request is verified in three independent layers.

**1. CI — `.github/workflows/ci.yml`.** Runs on every PR and every push to `main`:

| Gate | What it protects |
| --- | --- |
| `ruff check` + `ruff format --check` | style and import hygiene |
| `pytest` | the full suite: parsing, daily policy, ledger, privacy, security, persistence, telemetry |
| `pytest tests/probes` | offline regression probes kept as executable evidence |
| `scripts/check_claims.py` | every published number still matches the claims registry |
| `scripts/leakage_report.py --check-known` | known data leakage has not changed silently |
| `scripts/compare.py` | saved predictions still rescore identically |
| `test_daily_invariants.py` × 4 seeds | sheet/ledger invariants under randomised dates and orders |
| `gitleaks` | no secret reaches the repository |

CI deliberately runs with `EXTRACTOR_BACKEND=off`: a hosted call in CI once spent GPU
credit on every push. A green CI run is evidence the suite passed — it is not, by itself,
evidence that a browser-level run against a deployment happened.

**2. Per-PR preview deployment — `.github/workflows/preview.yml`.** Each non-draft PR gets
its own Render service (`tiffintally-pr-<number>`), its own URL, built from the PR's exact
commit. The workflow waits until the deployment is live *and* actually returns `200` on
`/health`, registers it as a GitHub deployment, and comments the URL on the PR. Preview
services are removed when the PR closes so free-tier slots are not exhausted. This is the
real, running artefact of the branch under review — not the production deployment.

**3. Third-party browser testing.** A separate automated UI test service runs generated
scenarios against the live deployment and reports back on the PR. Its setup and current
status are documented in `docs/TESTSPRITE_SETUP.md`.

## Deployment

Production is a Render free web service described by `render.yaml`, auto-deploying from
`main`. `GET /health` returns `{"status":"ok","version":"0.1.0"}`. Full notes, including
what is *not* deployed, are in `docs/DEPLOY.md`.

## Contributing and agent guidance

Read [`AGENTS.md`](AGENTS.md) before changing anything — it carries the shared engineering
rules, the concurrency rules for multiple agents working this repository at once, and the
PR verification workflow. [`docs/DEVELOPMENT_HANDOFF.md`](docs/DEVELOPMENT_HANDOFF.md) is
the current cross-session status board.

## Data and evidence

Train and legacy test are generated synthetic text with template-authored labels.
Legacy dev is contained in train. New dev2 is agent-authored synthetic development
text, not a blind human holdout. Frozen legacy files remain untouched. See
`docs/KNOWN_LEAKS.md`, `docs/POLICY.md`, and `HUMAN_TODO.md`.

## Privacy

By default (`TIFFINTALLY_PERSIST` unset or `0`) and in demo mode (`TIFFINTALLY_DEMO_MODE=1`),
sheets, reviews, and payment confirmations live strictly in ephemeral server memory for the browser
session and are never written to disk.

Persistent storage in SQLite (`data/tiffintally.db`) is an explicit opt-in gated behind `TIFFINTALLY_PERSIST=1`.
It is experimental: after a restart the sheet shows tokens, and the cutoff, target date, price and corrections are not restored. The reverse map is not encrypted. See `docs/KNOWN_GAPS.md`.
When persistence is enabled, one `Pseudonymizer` per upload replaces, before any write:

- every sender name in the export, its first word, and any roommate named in a message (`roommate Sneha`), with sequential tokens (`C001`, `C002`, and so on);
- phone numbers in the Indian formats people type, and email addresses;
- flat, house, plot and room numbers, and the building or society name that follows the number (`flat 402 Sai Heights`);
- the stored `orders.customer`, `orders.secondary_customer` and `orders.payment_note` fields, using the same token map.

Two limits, both stated rather than glossed over. A street name with no flat or building number in front of it (`Baner Road`) is not matched, so street names can remain in the masked text. Masking is pattern based, so an address phrased in a way no pattern recognises is not removed either. Because the stored customer name is already a token, a kitchen reloading from the database sees `C001`, not a name.

`tests/test_db_persistence.py` pastes a bracketed export and then reads the SQLite file (every table, plus the WAL and shared-memory bytes) and every file written under `data/`, including `data/private/`. That scan asserts that no name, phone number, email address or building name from the fixture is in those bytes. It also asserts that a bare street name is still there, so this section cannot quietly drift into a stronger claim than the code supports. The scan does not say that no name can ever reach disk: a street name can, and a session that is not the fixture is not what the test reads.

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

## Commits after the submission deadline

Repository created 13 Oct 2026. Any commit after 19 Oct 12:29 PM IST is listed here:

-
