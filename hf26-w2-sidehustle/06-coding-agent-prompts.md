# 06 — Sequenced Prompts (staged path)

Paste one per session. Each ends with: "update PROGRESS.md, run tests, commit, don't commit secrets, don't invent numbers."

**A. Baseline extractor.** "Implement `extract/gemma.py`: call Gemma via Google AI Studio (model name from env `GEMMA_MODEL`), JSON-schema prompt producing list[OrderEvent], pydantic validation, 2 retries, token+latency logging to `logs/calls.jsonl`. Pseudonymise customer names first (`privacy.py`). Add `tiffintally eval extract --model gemma` scoring field-level P/R/F1 and per-message exact match on data/synthetic test split and data/private/real_test.jsonl. Save to evals/runs/<ts>/."

**B. Reconciler + bold tests.** "Implement `reconcile.py` (pure function). Write every bold test in docs/07-evals.md section B. No mocking of the reconciler."

**C. Tinker FT.** "Read the current Tinker docs and supported-model list (don't guess the API). Build an SFT JSONL from the synthetic train split. LoRA fine-tune the smallest suitable model; record base model, rank, steps, lr, loss, cost in evals/runs/<ts>/tinker.json. Add `--model tinker` to eval. Compare on identical test sets. If it's worse, write why in RESULTS.md."

**D. TabPFN forecast.** "Use `tabpfn-client` (check the current docs for TabPFN-3.5 usage and auth). Implement `forecast.py` + `tiffintally eval forecast`: time-split, MAE/RMSE vs naive-lag7 and confirmed-only. Expose it as an agent tool `how_many_to_cook(date)`. If the history is synthetic, label it so in output."

**E. App UI.** "Mobile-first pages: upload, review (confidence < 0.7 highlighted, inline edit saves corrections), prep sheet (print CSS, packing labels), dues (drafted Hinglish reminders with a copy button; NO send). Demo mode uses synthetic data only."

**F. Voice brief.** "ElevenLabs TTS of a ≤60-word Hindi/English prep summary; cache by hash; log characters used; graceful fallback to text if the key is missing."

**G. Deploy.** "render.yaml (free plan), health route, start command. Write docs/DEPLOY.md for Vedant: env vars to set, custom domain steps for the .tech domain, and STOP if the dashboard asks for a card."

**H. Results + post.** "Generate RESULTS.md purely from evals/runs JSON (script it). Fill post.md from docs/09 template; every number links to a run file. Leave the FIRST USER section as `<<VEDANT FILLS>>`. Final gitleaks scan."
