# TiffinTally Build Progress

**Start Date:** 2026-10-13 13:30 IST  
**Target Deadline:** 2026-10-18 11:59 PM PDT (2026-10-19 12:29 PM IST)  
**Internal Feature Freeze:** 2026-10-19 09:00 AM IST

---

## Progress Log

### 2026-10-13 13:35 IST — P0: Repo & Foundation Setup
- [x] Initialized Git repository on `main` branch
- [x] Configured Python 3.11 with `uv`
- [x] Created `pyproject.toml` with FastAPI, Pydantic, TabPFN, Pytest, Ruff
- [x] Created `.gitignore` protecting secrets, `data/private/`, and databases
- [x] Created `.env.example` with clean placeholders
- [x] Created MIT `LICENSE`
- [x] Set up CI workflow `.github/workflows/ci.yml` (Ruff + Pytest + Secret leak guard)
- [x] Documented architectural decisions in `docs/DECISIONS.md`
- [x] Created `render.yaml` for free tier deployment

### 2026-10-13 13:45 IST — P1: Parser + Schema
- [x] Created `tiffintally/schema.py` (`ParsedMessage`, `OrderEvent`, `PackingLabel`, `CustomerLedger`, `DailyPrepSheet`)
- [x] Built `tiffintally/parser.py` supporting Android & iOS exports, 12h/24h timestamps, and multiline chats
- [x] Created realistic test chat fixtures in `tests/fixtures/`
- [x] Added `tests/test_parser.py` (6 passing unit tests)

### 2026-10-13 13:55 IST — P2: Synthetic Dataset & Human Labeling CLI
- [x] Built generator script `scripts/gen_synthetic.py` creating 655 realistic synthetic Hinglish messages
- [x] Split into 80/20 train/test: 524 in `data/synthetic/train.jsonl` and 131 in `data/synthetic/test.jsonl`
- [x] Built Typer interactive labeling CLI `scripts/label_cli.py`
- [x] Seeded held-out starter set `data/synthetic/real_benchmark_starter.jsonl` and placed in `data/private/real_test.jsonl` (gitignored)

### 2026-10-13 14:10 IST — P3: Privacy Pseudonymization & Teacher Extractor
- [x] Built client-side pseudonymizer `tiffintally/privacy.py` (local SQLite token mapping `C001..C999`)
- [x] Implemented zero-leakage guarantee in `tests/test_privacy.py`
- [x] Implemented `tiffintally/extract/base.py` with telemetry logger and robust heuristic rule-based fallback
- [x] Implemented Google AI Studio Gemma 2 extractor in `tiffintally/extract/gemma.py` with graceful offline fallback

### 2026-10-13 14:25 IST — P4: Deterministic Reconciler & The 12 Bold Tests
- [x] Built `tiffintally/reconcile.py` (timestamp-ordered replay, late cutoff filtering, secondary customer allocations, deduplication)
- [x] Implemented dues ledger with polite Hinglish reminder drafts (strict copy-to-clipboard, zero auto-send)
- [x] Implemented `tests/test_bold.py` covering all 12 mandatory edge cases and bold tests from prompt specification

### 2026-10-13 14:35 IST — P5: Tinker SFT Dataset & LoRA Extractor
- [x] Built `scripts/prepare_sft.py` generating 524 Chat SFT pairs in `data/synthetic/tinker_sft_train.jsonl`
- [x] Implemented Thinking Machines Tinker API extractor in `tiffintally/extract/tinker.py`
- [x] Validated surrogate offline fallback and SFT dataset formatting in `tests/test_tinker.py`

### 2026-10-13 14:45 IST — P6: TabPFN Kitchen Forecaster
- [x] Built `scripts/gen_history.py` generating 90 days of daily kitchen history (`data/kitchen_history.csv`) with DOW patterns and Indian festival holidays
- [x] Built `tiffintally/forecast.py` using Prior Labs TabPFN Regressor with 14-day holdout validation
- [x] Implemented `how_many_to_cook` decision tool anticipating late doorstep walk-ins
- [x] Added unit tests in `tests/test_forecast.py` (3 passing tests)

### 2026-10-13 14:55 IST — P7: Full FastAPI App UI & ElevenLabs Voice Briefing
- [x] Built mobile-friendly responsive kitchen web app in `tiffintally/app.py`
- [x] Built Jinja2 templates: `base.html`, `index.html`, `prep_sheet.html`, `ledger.html`, `forecast.html`
- [x] Built active learning correction endpoint `/api/corrections`
- [x] Implemented ElevenLabs morning Hinglish audio briefing in `tiffintally/voice.py`
- [x] Added `tests/test_app.py` and `tests/test_voice.py`

### 2026-10-13 15:05 IST — P8: Free Tier Deployment & Render Verification
- [x] Verified `render.yaml` specification with health check path `/health`
- [x] Added local production server CLI command `uv run tiffintally serve`
- [x] Confirmed zero live secrets and zero credit-card dependencies

### 2026-10-13 15:15 IST — P9: Comprehensive Evaluation Suite & RESULTS.md
- [x] Implemented end-to-end evaluation harness `tiffintally/eval.py` (F1, exact match, latency p50/p95, cost)
- [x] Added CLI command `uv run tiffintally eval all`
- [x] Ran evaluation suite and generated empirical `RESULTS.md` and `evals/runs/20261013_135155/summary.json`
- [x] Verified 44/44 green tests in pytest

### 2026-10-13 15:30 IST — P10: Dev.to Write-up & Demo Script
- [x] Created `post.md` following `hf26-w2-sidehustle/09-devto-post-template.md`
- [x] Created 60–90 second video recording script `docs/demo-script.md`
- [x] Verified complete traceability of all metrics in `post.md` to `RESULTS.md` and run artifacts
