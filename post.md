---
title: TiffinTally: A WhatsApp-to-Kitchen Prep Sheet with Honest Evals and Open-Weight AI
published: false
tags: devchallenge, hf26challenge, opensource, python
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

Home tiffin cooks in Pune, Bengaluru, and Mumbai cook 30 to 50 meals every day. Their customers order in Hinglish on WhatsApp, usually late in the evening:
- *"Kal lunch 2, dinner skip."*
- *"Aaj raat 1 thali, bina pyaaz lahsun."*
- *"Roommate left for home, cancel one thali from tomorrow."*

At 10 PM, after turning off the stoves, the cook copies these messages into a paper notebook. A missed cancellation is wasted groceries and cooking time; a missed extra order is a hungry customer and lost revenue.

A Google Form would be cleaner, but customers ignore itâ€”they already have the cook's WhatsApp chat open.

**TiffinTally** is a local-first, privacy-preserving order desk and kitchen prep sheet for tiffin cooks. You paste the raw WhatsApp export; TiffinTally:
1. **Masks sensitive PII** (phone numbers, street addresses, and customer names) locally in memory.
2. **Extracts structured orders** using open-weight models (Gemma 2 9B via Google AI Studio, Qwen2.5-3B on Modal, or local Ollama).
3. **Reconciles meal counts** against cutoff times and cancellation rules.
4. **Maintains a dues ledger** where payment claims in chat remain unconfirmed until the cook verifies receipt.
5. **Generates a clean kitchen prep sheet** with packing lines and dietary modification warnings.

### What the evaluation lab does and does not do

`/benchmarks` scores one extraction against a gold event and applies a set of hand-written repair rules. It is a demo of the scorer, not a quality claim:

- It needs gold labels, so it cannot run over real traffic.
- It starts from the offline rules or from an injected fake flaw. It never asks a model.
- Its repair rules were written for the same four sentences it scores, so a pass demonstrates the scorer, not general accuracy. One of the four does not pass.
- Pasting a chat never calls it.

The measured numbers in `RESULTS.md` come from `scripts/publish_results.py` rescoring saved per-row outputs, not from this page.

---

## Demo

### Run Locally in 60 Seconds

You can run TiffinTally entirely on your laptop with zero external cloud dependencies:

```bash
# Clone the repository
git clone https://github.com/Vedant817/tiffintally.git
cd tiffin-tally

# Install dependencies with uv
uv sync --all-extras --dev

# Start the web app
uv run tiffintally serve
```

Visit `http://127.0.0.1:8000` to paste a WhatsApp export and inspect the generated prep sheet and ledger.

Visit `http://127.0.0.1:8000/benchmarks` for the scorer demo: one sentence, its gold event, the score, and what the repair rules change.

### One-Click Deploy on Render

TiffinTally includes an official Render Blueprint specification (`render.yaml`). To deploy on Render:
1. Go to **Render Dashboard** > **Blueprints** > **New Blueprint Instance**.
2. Connect your fork of `Vedant817/tiffintally`.
3. Optionally set `GOOGLE_API_KEY` in environment settings to enable the open-weight Gemma 2 9B extractor.
4. Access `/health` and the live app on your Render URL.

---

## Code

{% github Vedant817/tiffintally %}

Key architectural modules:
- [`tiffintally/extract/gemma.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/extract/gemma.py): Multi-backend model router supporting Google AI Studio (`gemma-4-26b-a4b-it`), Modal (`Qwen2.5-3B`), local OpenAI/Ollama, or offline regex rules.
- [`tiffintally/benchmarks.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/benchmarks.py): Metric scorer and the hand-written repair rules used by the `/benchmarks` demo.
- [`tiffintally/privacy.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/privacy.py): In-memory pseudonymization replacing Indian mobile numbers, street addresses, and personal names with sequential tokens (`C001`, `C002`).
- [`tiffintally/db.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/db.py): ACID SQLite persistence layer gated behind `TIFFINTALLY_PERSIST=1`, storing only masked text to ensure unmasked phone numbers never touch disk.
- [`tiffintally/reconcile.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/reconcile.py): Daily order reconciliation, cutoff enforcement, and packing slip generation.

---

## How I Built It

### 1. Multi-Provider Open-Weight Routing

TiffinTally is engineered from the ground up around open-source AI and open-weight models:
- **Gemma 2 9B (`gemma-4-26b-a4b-it`)**: Google's instruction-tuned open-weight model accessed via Google AI Studio API for zero-cost hosted extraction.
- **Qwen2.5-3B**: Fine-tuned LoRA adapter served via Modal for fast batched extraction.
- **Local Ollama / vLLM**: Seamless compatibility with local endpoints via OpenAI-compatible schemas (`http://localhost:11434/v1`).
- **Offline Heuristic Engine**: Fast, deterministic regex rules that run offline with zero internet access when no API key is supplied.

### 2. Zero-Retention Privacy Architecture

Small kitchen businesses handle real customer phone numbers, home addresses, and apartment gate codes:
- **Default Ephemeral Mode**: By default and in demo mode (`TIFFINTALLY_PERSIST=0`), no chats, customer names, or orders are written to disk. All state resides in ephemeral server memory for the browser session.
- **Strict Masking on Disk**: When persistence is explicitly turned on (`TIFFINTALLY_PERSIST=1`), both `uploads.raw_text` and `orders.raw_text` are sanitized using `Pseudonymizer`. Real phone numbers like `+91 98765 43210` are replaced with tokens (`C001`, `C002`). Binary inspection tests in CI verify that raw phone numbers never appear anywhere in the `.db` file.

### 3. Scorer Demo

`/benchmarks` scores one sentence against its gold event using precision, recall, F1, strict and lenient match, schema and safety, then applies a few hand-written repair rules. Two properties matter and both are stated on the page: the rules were written for those same sentences, and the adversarial suite does not reach the threshold.

---

## Why Does Open Innovation Matter?

1. **Unit Economics for Small Businesses**: A tiffin cook selling home-cooked meals for â‚¹80 ($0.95) cannot spend $0.03 per customer chat on proprietary closed APIs. Open-weight models like Gemma 2 9B and Qwen2.5-3B make the unit economics viable at zero or near-zero marginal cost.
2. **Customer Privacy**: Home kitchen customers trust the cook with their home address and phone number. Open models can run on a local laptop via Ollama or with local pseudonymization, ensuring customer PII never leaves the cook's control.
3. **No Vendor Lock-In**: Because extraction relies on standard open-weight architectures, a cook or developer is never trapped by proprietary API deprecations or sudden price hikes.

---

## My Agent Session

TiffinTally was built, refactored, and verified with automated tests:
- Over 305 automated pytest unit and invariant tests covering edge-case parsers, privacy boundaries, and database gating.
- Every number in `RESULTS.md` and the README table is produced by `scripts/publish_results.py` rescoring saved per-row outputs; `scripts/check_claims.py` fails the build on an unregistered number.

---

## Prize Categories

### Best Use of Gemma
TiffinTally's hosted backend targets Google's open-weight **Gemma 4 26B** (`gemma-4-26b-a4b-it`) on Google AI Studio. No Gemma run has been measured yet: `RESULTS.md` records the Gemma baseline as NOT RUN for want of a key, so no accuracy is claimed here. The extractor is written so a judge can check it: it names the model that actually answered, skips reasoning parts, and falls back to the rules with the HTTP error shown rather than claiming a model answered.

### Best Use of Render
TiffinTally provides a zero-setup `render.yaml` Blueprint to deploy the FastAPI application on Render's cloud platform with Python 3.11, automatic dependency resolution with `uv`, demo mode isolation, and health check monitoring.
