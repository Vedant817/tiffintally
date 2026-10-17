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

A Google Form would be cleaner, but customers ignore it—they already have the cook's WhatsApp chat open.

**TiffinTally** is a local-first, privacy-preserving order desk and kitchen prep sheet for tiffin cooks. You paste the raw WhatsApp export; TiffinTally:
1. **Masks sensitive PII** (phone numbers, street addresses, and customer names) locally in memory.
2. **Extracts structured orders** using open-weight models (Gemma 2 9B via Google AI Studio, Qwen2.5-3B on Modal, or local Ollama).
3. **Reconciles meal counts** against cutoff times and cancellation rules.
4. **Maintains a dues ledger** where payment claims in chat remain unconfirmed until the cook verifies receipt.
5. **Generates a clean kitchen prep sheet** with packing lines and dietary modification warnings.

### The Honest-Evals Angle: Standing Apart from the Crowd

Other submissions in this space have claimed 100% accuracy on synthetic WhatsApp chats or showcased TabPFN plate forecasts that claim to save thousands of rupees a month.

When we actually audited messy WhatsApp text against open-weight models, we discovered the unvarnished reality:
- Models frequently hallucinate on **negated cancellations**: *"don't send lunch"* gets misparsed as *`meal: lunch, qty: 1`*.
- Hindi number words (*"ek"*, *"do"*, *"teen"*) and roommate split orders (*"cancel for Rahul, keep mine"*) lead to missed plates.
- Dietary restrictions (*"bina mirch"*, *"jain"*) often get dropped, risking allergic or religious customer conflicts.

Instead of hiding behind cherry-picked synthetic numbers, TiffinTally introduces an **AI Benchmark & Self-Healing Evaluation Lab** (`/benchmarks`). It continuously evaluates open-weight model outputs across 7 quantitative metrics (Precision, Recall, Micro F1, Strict/Lenient Accuracy, Schema Adherence, and Guardrail Safety). When an extraction falls below the 90% benchmark threshold, an automated self-healing retry loop applies diagnostic repair heuristics until the output passes before any prep sheet hits the kitchen.

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

Visit `http://127.0.0.1:8000/benchmarks` to access the interactive **AI Evaluation Lab** and test automated self-healing retries against real edge-case suites.

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
- [`tiffintally/extract/gemma.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/extract/gemma.py): Multi-backend model router supporting Google AI Studio (`gemma-2-9b-it`), Modal (`Qwen2.5-3B`), local OpenAI/Ollama, or offline regex rules.
- [`tiffintally/benchmarks.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/benchmarks.py): Quantitative metrics calculator, diagnostic repair rules, and self-healing retry loop.
- [`tiffintally/privacy.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/privacy.py): In-memory pseudonymization replacing Indian mobile numbers, street addresses, and personal names with sequential tokens (`C001`, `C002`).
- [`tiffintally/db.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/db.py): ACID SQLite persistence layer gated behind `TIFFINTALLY_PERSIST=1`, storing only masked text to ensure unmasked phone numbers never touch disk.
- [`tiffintally/reconcile.py`](https://github.com/Vedant817/tiffintally/blob/main/tiffintally/reconcile.py): Daily order reconciliation, cutoff enforcement, and packing slip generation.

---

## How I Built It

### 1. Multi-Provider Open-Weight Routing

TiffinTally is engineered from the ground up around open-source AI and open-weight models:
- **Gemma 2 9B (`gemma-2-9b-it`)**: Google's instruction-tuned open-weight model accessed via Google AI Studio API for zero-cost hosted extraction.
- **Qwen2.5-3B**: Fine-tuned LoRA adapter served via Modal for fast batched extraction.
- **Local Ollama / vLLM**: Seamless compatibility with local endpoints via OpenAI-compatible schemas (`http://localhost:11434/v1`).
- **Offline Heuristic Engine**: Fast, deterministic regex rules that run offline with zero internet access when no API key is supplied.

### 2. Zero-Retention Privacy Architecture

Small kitchen businesses handle real customer phone numbers, home addresses, and apartment gate codes:
- **Default Ephemeral Mode**: By default and in demo mode (`TIFFINTALLY_PERSIST=0`), no chats, customer names, or orders are written to disk. All state resides in ephemeral server memory for the browser session.
- **Strict Masking on Disk**: When persistence is explicitly turned on (`TIFFINTALLY_PERSIST=1`), both `uploads.raw_text` and `orders.raw_text` are sanitized using `Pseudonymizer`. Real phone numbers like `+91 98765 43210` are replaced with tokens (`C001`, `C002`). Binary inspection tests in CI verify that raw phone numbers never appear anywhere in the `.db` file.

### 3. AI Evaluation Lab & Automated Self-Healing

The hardest part of parsing chat exports with an LLM is handling negated instructions, roommate splits, and dietary restrictions:
- We built `/benchmarks` with 4 test suites:
  1. *Negated Intent*: *"kal lunch mat bhejna"* (don't send lunch) vs extra orders.
  2. *Dietary Allergens*: *"bina pyaz lahsun / jain thali"* (no onion/garlic).
  3. *Roommate Splits*: *"cancel for Rahul, add one for me"*.
  4. *Adversarial Guardrails*: Prompt injection and delimiter escaping attempts.
- When an open model extraction fails, TiffinTally's repair heuristics diagnose the error type (`MODS_MISMATCH`, `NEGATED_CANCELLATION`, `SPLIT_ROOMMATE`), heal the event payload, and iterate until passing the $\ge 90\%$ benchmark threshold.

---

## Why Does Open Innovation Matter?

1. **Unit Economics for Small Businesses**: A tiffin cook selling home-cooked meals for ₹80 ($0.95) cannot spend $0.03 per customer chat on proprietary closed APIs. Open-weight models like Gemma 2 9B and Qwen2.5-3B make the unit economics viable at zero or near-zero marginal cost.
2. **Customer Privacy**: Home kitchen customers trust the cook with their home address and phone number. Open models can run on a local laptop via Ollama or with local pseudonymization, ensuring customer PII never leaves the cook's control.
3. **No Vendor Lock-In**: Because extraction relies on standard open-weight architectures, a cook or developer is never trapped by proprietary API deprecations or sudden price hikes.

---

## My Agent Session

TiffinTally was built, refactored, and verified with deep autonomous testing:
- Over 305 automated pytest unit and invariant tests covering edge-case parsers, privacy boundaries, and database gating.
- Full collaborative browser verification using real browser sessions to navigate the UI, test flawed extractions, and watch the self-healing retry loop achieve 100% benchmark scores in real time.

---

## Prize Categories

### Best Use of Gemma
TiffinTally uses Google's open-weight **Gemma 2 9B** (`gemma-2-9b-it`) via Google AI Studio as its default hosted extraction engine. It routes pseudonymized Hinglish WhatsApp orders through Gemma's JSON schema generation API, extracting meal counts, dietary constraints, and cancellation intents with high fidelity.

### Best Use of Render
TiffinTally provides a zero-setup `render.yaml` Blueprint to deploy the FastAPI application on Render's cloud platform with Python 3.11, automatic dependency resolution with `uv`, demo mode isolation, and health check monitoring.
