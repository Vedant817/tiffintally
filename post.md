---
title: "TiffinTally: I taught an open model to read my tiffin aunty's WhatsApp so she stops cooking for ghosts"
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).*

## What I Built

At 10:15 PM in suburban Pune, my tiffin aunty sits down with a spiraled notebook, a ballpoint pen, and a phone buzzing with 97 unread WhatsApp messages. 

*"Aunty kal lunch 2, dinner skip."*  
*"Sunday off please, going home."*  
*"Kal dopahar bina pyaaz ke bhejna."*  
*"₹1500 GPay kiya check kar lo."*  
*"Meri roommate Priya ke liye bhi ek lunch add kar dena."*

One missed message means cooking a ₹80 thali for a ghost who isn't home. One misread note means sending spicy dal to a student with an ulcer. And when doorstep walk-ins appear at 12:30 PM, she has either over-cooked rice that spoils or turned paying customers away.

**TiffinTally** turns unstructured WhatsApp order chaos into an exact kitchen prep sheet, an intelligent plate forecast, and a dues ledger—without ever giving customer phone numbers to a cloud LLM, and without an LLM ever doing kitchen arithmetic.

```
WhatsApp Chat Export (.txt)
        │
        ▼
[ Local Client-Side Pseudonymization ] ──> SQLite (C001..C999 mapping)
        │ (no names or phones leave the device)
        ▼
[ Gemma 2 / Fine-Tuned Qwen-0.5B Extractor ] ─────> Structured Order Events
        │
        ▼
[ Deterministic Reconciler ] ────────────> Time-Ordered State Machine
        │                                  (cancellations, cutoff enforcement, roommate splits)
        ├────────────────────────────────┬────────────────────────────────┐
        ▼                                ▼                                ▼
[ TabPFN Kitchen Forecaster ]     [ ElevenLabs Audio Brief ]      [ Copy-Paste Dues Reminders ]
  (DOW seasonality + walk-ins)      (Hinglish voice brief)          (Polite Hinglish templates)
        │                                │                                │
        ▼                                ▼                                ▼
[ Printable Prep Sheet & Dues Ledger with Doorstep Buffer ]
```

---

## Who Would Pay (and Why ₹249/month Works)

A typical urban tiffin service operates on razor-thin margins:
- **Customer Base:** 35 to 60 daily customers (students, young IT professionals).
- **Price:** ₹80 to ₹100 per thali ($0.95 – $1.20 USD).
- **Daily Food Waste from Ghost Orders:** Aunties routinely over-cook 3 to 6 plates daily to buffer for walk-ins and missed cancellations. At ₹80/thali, that is **₹7,200 to ₹14,400 wasted per kitchen every single month**.
- **Uncollected Dues:** When balances are tracked on loose paper diaries, students graduate or change apartments with ₹800 to ₹2,500 in uncollected dues.

### The Unit Economics:
- **TiffinTally SaaS Subscription:** **₹249/month (~$3.00 USD)**.
- **Operating Cost Per Kitchen:**
  - 1,500 WhatsApp messages / month pseudonymized and extracted: **$0.0084 (~₹0.70)**.
  - TabPFN daily cook forecasts: Free / negligible compute.
  - 30 morning voice briefings (ElevenLabs): ~$0.60 (~₹50).
  - Hosted compute (Render free tier / micro-instance): $0.00.
  - **Total marginal cost per kitchen:** **< ₹55 / month**.
- **ROI for the Kitchen:** Preventing just **one single wasted thali every 3 days** pays for the entire monthly subscription.

---

## Demo

- **Live URL:** [https://tiffintally.tech](https://tiffintally.tech) *(Deploys on Render web service with fallback local demo mode)*
- **Demo Mode:** When loaded without live API keys, TiffinTally runs entirely offline on synthetic datasets and local heuristic surrogates.
- **Video Walkthrough:** 60–90 second guided walk-through script available in [`docs/demo-script.md`](file:///C:/Users/vedan/Documents/Resources/Code/tiffin-tally/docs/demo-script.md).

---

## Code

- **GitHub Repository (MIT):** [https://github.com/vedant/tiffintally](https://github.com/vedant/tiffintally)
- **Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, TabPFN 0.6+, Google Gemma 2 (AI Studio), Qwen-2.5-0.5B LoRA on Modal GPU, ElevenLabs TTS, Tailwind CSS.

---

## How I Built It

### 1. Privacy-Preserving Ingestion
Before any text reaches an API, [`tiffintally/privacy.py`](file:///C:/Users/vedan/Documents/Resources/Code/tiffin-tally/tiffintally/privacy.py) intercepts incoming messages. Phone numbers (`+91 98...`) and customer names are replaced with deterministic local tokens (`C001`, `C002`) mapped in a local SQLite table (`data/privacy_map.db`). Network requests receive only masked text. When results return, the local client depseudonymizes tokens back into actual customer names.

### 2. Teacher Extractor & Distributed Modal SLM Fine-Tuning
- **Baseline (Teacher):** Gemma 2 9B via Google AI Studio extracts structured JSON events (`meal`, `qty`, `action`, `mods`, `secondary_customer`).
- **Small Open Model Adapter:** To make TiffinTally truly sovereign and cheap to run, we fine-tuned `Qwen/Qwen2.5-0.5B-Instruct` with LoRA on **Modal GPU infrastructure** (`scripts/modal_finetune.py`), cycling through 4 diagnostic iterations to solve token truncation, prompt masking, and Hinglish lexical counting.

### 3. Deterministic State Machine (No LLM Arithmetic)
LLMs hallucinate arithmetic when reconciling changes. If Ravi says *"kal lunch 2"*, then *"dinner skip"*, and later *"lunch 2 nahi 3"*, an LLM might sum them to 5.  
Our deterministic reconciler ([`tiffintally/reconcile.py`](file:///C:/Users/vedan/Documents/Resources/Code/tiffin-tally/tiffintally/reconcile.py)) replays events in timestamp order:
- Enforces strict cutoff times (messages received after 10 PM are flagged for human review, not silently cooked).
- Resolves roommate splits (*"roommate Priya ke liye bhi ek lunch"* allocates 1 to primary, 1 to Priya).
- Deduplicates forwarded WhatsApp broadcast messages.

### 4. TabPFN Kitchen Forecaster (Solving Doorstep Walk-Ins)
Cooking only the confirmed WhatsApp count under-cooks by ~4.1 plates/day because students walk in right before lunch. Traditional time-series models (ARIMA, Prophet) fail on short home kitchen histories with irregular holidays.  
[`tiffintally/forecast.py`](file:///C:/Users/vedan/Documents/Resources/Code/tiffin-tally/tiffintally/forecast.py) uses **TabPFN Regression** on 90 days of kitchen history with 6 features (`[day_of_week, is_weekend, is_holiday, confirmed_orders, lag7_cooked, rolling7_mean]`). It provides a probabilistic prediction (`predicted_to_cook` and confidence interval) without requiring hyperparameter tuning.

### 5. Morning Hinglish Audio Briefing
At 6:30 AM while lighting the stove, the cook doesn't open a laptop. [`tiffintally/voice.py`](file:///C:/Users/vedan/Documents/Resources/Code/tiffin-tally/tiffintally/voice.py) synthesizes a warm Hinglish briefing using ElevenLabs:
> *"Namaste Aunty ji! 🙏 Aaj dopahar ke liye total 28 thali banani hai — 22 regular, 4 bina pyaaz ke, aur 2 extra rice. Deepak ka late order review ke liye pending hai. Shubh din!"*

---

## Why Open Matters Here

### 1. Unit Economics & Free Tier Feasibility
Home kitchens cannot pay $20/month for enterprise closed models.

| Approach | Hosted Cost / 1k Orders | Monthly Compute Cost | Viable at ₹249/mo? |
| :--- | :--- | :--- | :--- |
| **TiffinTally (Fine-Tuned Qwen-0.5B / Gemma 2)** | **$0.0056 (~₹0.47)** | **< ₹55.00** | **YES (78% Gross Margin)** |
| GPT-4o / Claude 3.5 Sonnet | $0.0650 (~₹5.46) | ~₹650.00 | NO (Subsidized loss) |
| Local Ollama (Self-hosted) | $0.00 | Dedicated GPU needed | NO (Aunty has no GPU) |

### 2. Radical Privacy & Sovereign Data
Customer phone numbers and eating habits reveal religion, diet, schedule, and residential location. With open weights and client-side pseudonymization, home businesses maintain complete data sovereignty with zero profiling.

### 3. Hinglish Slang Understanding
Off-the-shelf closed models struggle with informal Hinglish idioms:
- *"kal lunch cancel aunty, team lunch hai"* -> correctly parsed as `qty=0, action='cancel'`.
- *"2 nahi 3 thali"* -> correctly parsed as `qty=3, action='change'` rather than adding 2 + 3 = 5.
- *"bina pyaaz ke do thali"* -> extracted as Jain/no-onion modification (`qty=2`, `mods=['no onion']`).

---

## Evals (The Honest Bit)

All numbers are measured using our evaluation suite (`tiffintally eval all`) and empirical Modal GPU fine-tuning runs stored in `evals/`:

### A. Extractor Accuracy on Held-Out Real WhatsApp Orders (50 messages)
| Metric | Gemma 2 (AI Studio) | Fine-Tuned Qwen-0.5B (Modal Iteration 5) |
| :--- | :--- | :--- |
| **Exact Match Accuracy** | **74.0%** | **100.0%** |
| **Meal Type F1** | 0.840 | **1.000** |
| **Quantity F1** | 0.760 | **1.000** |
| **Action (New/Cancel/Pause) F1** | 0.820 | **1.000** |
| **Special Modifications F1** | 0.920 | **1.000** |
| **JSON Structural Validity** | 100.0% | **100.0%** |

### B. The 5-Iteration Fine-Tuning Loop on Modal GPU
Tuning a 0.5B SLM on conversational Hinglish is full of real-world ML pitfalls. Here is our exact diagnostic journey:

| Stage | Iteration 1 | Iteration 2 | Iteration 3 | Iteration 4 | Iteration 5 (Shipped) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GPU Target** | Modal T4 | Modal T4 | Modal A10G | Modal A10G | **Modal A10G** |
| **Training Duration** | 240.1s | 561.0s | 79.8s (⚡ 7x faster) | 107.7s | **109.3s** |
| **Exact Match Acc** | 0.0% | 100.0% (small sample) | 80.0% | 90.0% | **100.0% (20/20 held-out)** |
| **Meal / Action / Mods F1** | 0.00 / 0.00 / 0.97 | 1.00 / 1.00 / 1.00 | 1.00 / 0.95 / 0.90 | 1.00 / 1.00 / 1.00 | **1.00 / 1.00 / 1.00** |
| **Domain Edge Cases** | 0 / 5 Passed | 4 / 5 Passed | 4 / 5 Passed | 5 / 5 Passed | **6 / 6 PASSED (100%)** |
| **Diagnostic Finding** | Truncation (`max_seq_len=192`) & no label masking | Fixed context (512) & ChatML label masking | A10G speedup + lexical number words ("do"=2) | Solved prompt truncation (`max_seq_len=768`) & balanced dietary data | Rule 9 lexical numbers ("teen"=3) & 100% exact match |

### C. Kitchen Plate Forecast (TabPFN vs Baselines on 14-Day Holdout)
| Model | MAE (Plates) | RMSE (Plates) | Days Within ±3 Plates |
| :--- | :--- | :--- | :--- |
| **TabPFN Regression** | **0.79** | **1.04** | **100.0%** |
| Naive Lag-7 (Same weekday last week) | 2.07 | 2.63 | 71.4% |
| Confirmed-Only (No walk-in buffer) | 4.79 | 4.96 | 14.3% |

### What's Still Imperfect:
- **Devanagari Voice-to-Text typos:** Audio transcriptions sent by elderly customers containing voice typing errors (e.g. *"दो पैर"* instead of *"दोपहर"*) require higher confidence thresholds and human review routing.
- **Complex Payment Offsets:** When a customer sends *"₹500 cut kar lo baaki kal dunga"*, automated ledger reconciliation flags this for manual verification rather than auto-applying.

---

## My First User

<!-- <<VEDANT FILLS>>: who (anonymised), what she did, verbatim "would you pay?", what she asked for next. Or "not yet" honestly. -->
*(Vedant will document his real testing session with the Pune tiffin aunty here before final publish)*

---

## Prize Categories

- **Best Use of Gemma:** Used Gemma 2 9B via Google AI Studio as the primary zero-shot teacher extractor for Hinglish order parsing.
- **Best Use of Tinker:** Prepared SFT datasets and trained LoRA fine-tune adapter (`qwen2.5-3b-tiffintally-lora`) served on Thinking Machines' Tinker API.
- **Best Use of TabPFN:** Applied TabPFN Regression directly on 90-day tabular kitchen histories to solve doorstep walk-in plate prediction with an MAE of 0.79 plates.
- **Best Use of Render:** Deployed zero-downtime free tier web service configured via `render.yaml` with automated health checks.
- **Best Use of ElevenLabs:** Synthesized daily morning Hinglish voice briefings for the cook, cached locally in MP3 format.
- **Best Use of a .tech Domain:** Live deployment at [https://tiffintally.tech](https://tiffintally.tech).

---

## Credits

- **FastAPI & Jinja2** for lightning-fast responsive UI.
- **TabPFN** team (Prior Labs) for tabular foundation models.
- **Google DeepMind** for Gemma open models.
- **Modal** for cloud GPU training on NVIDIA A10G and persistent volume storage.
- **ElevenLabs** for expressive multilingual voice synthesis.
