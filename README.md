# TiffinTally 🍲

> *"Your WhatsApp orders, sorted before the pressure cooker's first whistle."*

Built for **DEV Hacktoberfest 2026 Week 2: "Side Hustle"** by **Vedant Mahajan**.

[![CI](https://github.com/Vedant817/tiffintally/actions/workflows/ci.yml/badge.svg)](https://github.com/Vedant817/tiffintally/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Test Suite](https://img.shields.io/badge/tests-71%20passed-brightgreen.svg)](tests/)
[![Accuracy](https://img.shields.io/badge/Real%20WhatsApp%20EM-100.0%25-success.svg)](RESULTS.md)
[![Edge Footprint](https://img.shields.io/badge/Edge%20LoRA-8.6%20MB-blue.svg)](tiffintally/edge.py)
[![Observability](https://img.shields.io/badge/Telemetry-Sentry%20Tracing-purple.svg)](tiffintally/telemetry.py)

---

## The Problem

A home tiffin cook in Pune or Bengaluru serves 30–50 customers (PG students, office workers, young professionals). Every evening between 9:00 PM and 11:30 PM, 60–120 messy WhatsApp messages roll in:
- *"Aunty kal lunch 2, dinner cancel"*
- *"Kal 2 nahi 3 thali dinner bhejo"*
- *"Aaj roti nahi extra rice please, bina pyaaz ke"*
- *"Priya ke liye bhi ek lunch add kar dena"*
- *"₹1500 GPay kiya aunty check kar lo"*
- *"Send dinner tonight by 8:30 pm sharp, 1 thali"*
- WhatsApp voice notes: *"Aunty suno kal lunch cancel rakhna, office me lunch party hai"*

She tallies by hand late at night in a grease-stained notebook, often misses cancellations, over-cooks 4–5 extra thalis that spoil by morning, and loses track of monthly customer dues.

---

## The Solution: TiffinTally

1. **Zero-API-Fee Ingestion:** Ingest standard WhatsApp export `.txt` files or raw text paste. No WhatsApp Business API fees or account bans.
2. **Multimodal WhatsApp Voice Note Transcription:** Ingest `.ogg`, `.opus`, `.m4a`, and `.mp3` audio voice notes from customers, transcribing spoken Hinglish instructions directly into structured order lines.
3. **Touch-Friendly Kitchen Display System (KDS / Station Mode):** Big tap targets designed for grease-resistant tablet operation on kitchen countertops, with live container ticking, lunch/dinner station filters, and real-time packing progress bars.
4. **Client-Side Privacy Pseudonymization:** All customer names and phone numbers are converted to client-side tokens (`C001`, `C002`) in local SQLite before inference. Phone numbers never leave the cook's device.
5. **Adversarial Input Guardrail:** Regex-based sanitization strips ChatML/Llama prompt injection delimiters (`<|im_start|>`), normalizes Unicode homoglyphs, and clamps excessive single orders (`qty <= 20`).
6. **Structured Open-Weight Extraction:** 3 certified LoRA production tiers trained on Modal GPU / Thinking Machines' Tinker platform, achieving **100.0% Exact Match on real WhatsApp orders** with **sub-300ms p50 latency**.
7. **Active Learning Feedback Flywheel:** Human corrections entered on the prep screen or KDS are persisted to `data/private/corrections.jsonl` and can be exported as deduplicated ChatML SFT batches for continuous fine-tuning.
8. **Deterministic Reconciler:** Pure Python logic applies cancellations, modifications, and secondary customer allocations in chronological order, flagging late messages past cutoff.
9. **Kitchen Recipe Bill of Materials (BOM):** Automated ingredient scaling (exact kg of Atta, Dal, seasonal vegetables, rice, packaging) for the day's prep.
10. **Intelligent Kitchen Forecast:** Prior Labs `TabPFN` Bayesian foundation model predicts actual plates to cook based on day-of-week and kitchen history (**0.79-plate MAE**, saving ₹4,218/month in food waste).
11. **Morning Audio Brief:** ElevenLabs voice brief summarizing the day's prep in 30 seconds while the cook kneads dough.
12. **Polite Dues Ledger:** Tracks balances and drafts respectful Hinglish reminders with a one-click copy button (never auto-sent).
13. **Distributed Pipeline Tracing & Sentry Observability:** End-to-end tracing on transcription, guardrail sanitization, extraction latency, and instant security alerts on prompt injection attempts.

---

## Certified Production Model Tiers

Following a 30-iteration empirical training campaign on Modal A10G GPUs, we isolated three distinct production deployment profiles:

| Deployment Tier | Champion Run | Trainable Params | Disk / RAM Footprint | Real WhatsApp Exact Match | p50 Latency | Hardware Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Edge Champion** | **Iteration 30** | **2.16M (0.435%)** | **8.6 MB** | **100.0% (50/50)** | **286.8 ms** | Raspberry Pi 5, Kitchen POS tablets, offline laptops |
| **Tier 2: Mid-Size Champion** | **Iteration 28** | **8.80M (1.750%)** | **35.2 MB** | **100.0% (50/50)** | **445.5 ms** | $5/month VPS, Docker microservices |
| **Tier 3: Cloud Grand Champion** | **Iteration 25** | **17.60M (3.439%)** | **70.4 MB** | **100.0% (50/50)** | **452.8 ms** | High-throughput serverless vLLM clusters |

---

## Quickstart

```bash
# 1. Clone repository
git clone https://github.com/Vedant817/tiffintally.git
cd tiffintally

# 2. Install dependencies with uv
uv sync

# 3. Run test suite (71 tests across 15 test suites)
uv run pytest

# 4. Launch local server
uv run tiffintally serve
```

Visit `http://localhost:8000` to try the kitchen operating system with pre-loaded demo data!
Visit `http://localhost:8000/station` to see the touch-friendly Kitchen Display Station!

---

## CLI Utilities

```bash
# Parse a WhatsApp chat export file
uv run tiffintally parse my_chat.txt --date tomorrow

# Predict kitchen plate demand using TabPFN
uv run tiffintally forecast --confirmed 42

# Benchmark offline edge quantized execution on current hardware
uv run tiffintally benchmark-edge --tier all

# Export Ollama / GGUF deployment manifest and adapter configuration
uv run tiffintally export-edge --tier tier1_edge

# Export recorded cook corrections into an SFT JSONL training batch
uv run tiffintally export-sft
```

---

## Interactive Evaluation Dashboard

Launch the visual analytics dashboard to explore the 30-iteration training trajectory, loss curves, and benchmark comparisons:
```bash
# Open dashboard in your default browser
open evals/dashboard.html
```

---

## Architecture

```
[ Customer WhatsApp Chat Export (.txt / voice notes) ]
                        │
                        ▼
            [ Layer 1: InputGuardrail ]
   (Strips <|im_start|>, detects prompt injection, clamps qty<=20)
                        │
                        ▼
       [ Layer 2: Client-side Pseudonymizer ]
       (Names mapped to C001..C999 in local SQLite)
                        │
                        ▼
      [ Layer 3: Open-Weight Extractor Tiers ]
      ├── Tier 1 (Edge LoRA): 2.16M params, 8.6MB (286ms p50)
      ├── Tier 2 (VPS LoRA):  8.80M params, 35MB (445ms p50)
      ├── Tier 3 (Cloud LoRA): 17.6M params, 70MB (452ms p50)
      └── Heuristic Deterministic Fallback Engine
                        │
                        ▼
         [ Layer 4: Deterministic Reconciler ]
   (Time-ordered replay, cutoff flags, secondary allocations)
         ┌──────────────┬──────────────┬──────────────┬──────────────┐
         ▼              ▼              ▼              ▼              ▼
   [ Prep Sheet ] [ Station KDS ] [ Dues Ledger ] [ Recipe BOM ] [ Feedback ]
   & Stickers     & Touch Box     & Reminders     & Groceries    & Active SFT
         │                                            │
         ▼                                            ▼
   [ ElevenLabs ]                              [ Prior Labs ]
   Morning TTS                                 TabPFN Demand
   Audio Brief                                 Forecaster (0.79 MAE)
```

---

## Unit Economics & Food Waste ROI

For a 45-thali daily home kitchen in Pune:
- **Food Waste Saved (TabPFN)**: Prevents 3.7 wasted plates per day = **₹4,218 / month saved** in raw groceries.
- **Uncollected Dues Recovered**: Polite Hinglish drafts = **+₹4,100 / month recovered**.
- **AI Inference Marginal Cost**: Fine-tuned open SLM on local CPU = **₹0.00** (vs ₹230/mo for GPT-4o APIs).
- **Subscription Price**: **₹249 / month** (~18x return on investment for the home cook).

---

## Testing & Quality Assurance

71 automated test suites run on every commit:
```bash
uv run pytest
# Output: 71 passed, 1 warning in 27.9s (100% pass rate)
```

- `tests/test_security.py`: Input sanitization, delimiter stripping, injection blocking, quantity bounds.
- `tests/test_economics.py`: Kitchen grocery BOM scaling, AI unit economics, TabPFN waste ROI.
- `tests/test_edge.py`: Edge quantized benchmarking and GGUF/Ollama manifest export.
- `tests/test_feedback.py`: Cook correction persistence and ChatML SFT active learning export.
- `tests/test_transcribe.py`: WhatsApp voice note multimodal transcription and fallback.
- `tests/test_telemetry.py`: Sentry distributed tracing spans and security incident capture.
- `tests/test_bold.py`: 12 complex Hinglish slang and conversational edge cases.
- `tests/test_reconcile.py`: Deduplication, cutoff thresholding, cancellation propagation.
- `tests/test_forecast.py`: TabPFN demand regression and feature matrix formatting.
- `tests/test_privacy.py`: HMAC-SHA256 pseudonymization and de-anonymization.

---

## Evaluation & Honest Benchmarks

All benchmark tables are generated from reproducible runs in `evals/runs/`. See [`RESULTS.md`](./RESULTS.md) for full metrics, cost breakdowns per 1,000 messages, and failure mode analysis.

---

## License

MIT © [Vedant Mahajan](https://github.com/Vedant817)
