# TiffinTally 🍲

> *"Your WhatsApp orders, sorted before the pressure cooker's first whistle."*

Built for DEV Hacktoberfest 2026 Week 2: "Side Hustle" by **Vedant Mahajan**.

[![CI](https://github.com/vedantmahajan/tiffintally/actions/workflows/ci.yml/badge.svg)](https://github.com/vedantmahajan/tiffintally/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

---

## The Problem

A home tiffin cook in Bengaluru serves 30–50 customers (PG students, office workers, young professionals). Every evening, 60–120 messy WhatsApp messages roll in:
- *"Aunty kal lunch 2, dinner cancel"*
- *"Aaj roti nahi rice"*
- *"Priya ke liye bhi ek"*
- *"₹1500 GPay kiya aunty"*
- *"Sunday off"*

She tallies by hand at 10 PM in a physical notebook, often misses cancellations, cooks too much or too little, and loses track of monthly dues.

## The Solution: TiffinTally

1. **Ingest:** Ingest standard WhatsApp export `.txt` files or raw text paste. No WhatsApp Business API fees or account bans.
2. **Privacy Pseudonymization:** All customer names and phone numbers are converted to client-side tokens (`C001`, `C002`) before any hosted inference.
3. **Structured Extraction:** Open-weight models (Tinker LoRA on open LLMs; Google Gemma baseline/teacher) extract structured `OrderEvent` records.
4. **Deterministic Reconciler:** Pure Python logic applies cancellations, modifications, and standing orders in chronological order, flagging late messages past cutoff.
5. **Intelligent Kitchen Forecast:** Prior Labs `TabPFN` predicts actual plates to cook based on day-of-week, Indian holidays, and historical lag features.
6. **Polite Dues Ledger:** Tracks balances and drafts respectful Hinglish reminders with a one-click copy button (never auto-sent).
7. **Morning Audio Brief:** ElevenLabs voice brief summarizing the day's prep in 30 seconds.

---

## Quickstart

```bash
# 1. Clone repository
git clone https://github.com/vedantmahajan/tiffintally.git
cd tiffintally

# 2. Install dependencies with uv
uv sync

# 3. Launch local server
uv run tiffintally serve
```

Visit `http://localhost:8000` to try the app with pre-loaded demo data!

---

## Architecture

```
WhatsApp Export (.txt / paste)
      │
      ▼
┌───────────────────────────────┐
│  WhatsApp Multi-Format Parser │  (Android/iOS, 12h/24h, multiline)
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│ Client-side Pseudonymizer     │  (Names mapped to C001..C999 in local SQLite)
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│ Hosted Open Model Extractor   │  (Tinker LoRA fine-tune / Gemma 2/3 baseline)
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│ Pure Deterministic Reconciler │  (Time-ordered apply, cutoff flags, zero math drift)
└──────┬───────────────┬────────┘
       │               │
       ▼               ▼
┌─────────────┐ ┌───────────────┐
│ Prep Sheet  │ │ Dues Ledger   │
│ & Labels    │ │ & Reminders   │
└──────┬──────┘ └───────────────┘
       │
       ├────────────────────────┐
       ▼                        ▼
┌──────────────┐         ┌──────────────┐
│ Prior Labs   │         │ ElevenLabs   │
│ TabPFN Model │         │ Morning TTS  │
│ (Forecast)   │         │ (Briefing)   │
└──────────────┘         └──────────────┘
```

---

## Evaluation & Honest Benchmarks

All benchmark tables are generated from reproducible runs in `evals/runs/`. See [`RESULTS.md`](./RESULTS.md) for full metrics, cost breakdowns per 1,000 messages, and failure mode analysis.

---

## License

MIT © [Vedant Mahajan](https://github.com/vedantmahajan)
