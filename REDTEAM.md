# TiffinTally red-team (repo Vedant817/tiffintally @ a3241cf, reviewed 14 Oct 2026, 7:30 PM IST)

Time left: about 4.5 days (deadline Mon 19 Oct, 12:29 PM IST).
Commands run: `uv sync` (ok), `uv run pytest -q` (71 passed in 6.6s), `tiffintally eval` (fails: "Missing command"), `tiffintally benchmark-edge`, data-overlap script, parser and reconciler probes, a history grep for secrets, `curl https://tiffintally.tech`.

## Verdict
The plumbing is real: the parser, reconciler, FastAPI app and CI exist, and the tests pass. But the headline story is **not backed by the repo, and parts of it read as fabricated**:
- "100% real WhatsApp EM" is measured on a set that is 86% copied word for word into the training data.
- The Tinker prize claim describes a fine-tune that never happened on Tinker.
- The TabPFN number came from a scikit-learn fallback.
- The "edge benchmark" is `time.sleep` plus hardcoded numbers.
- The first-user story has verbatim quotes that were committed before the features they praise existed.
- The live domain doesn't resolve.

A judge who opens the repo for 10 minutes will find most of this. As it stands, **do not submit**. It's fixable in about 2 days if you cut the claims down to what's true and add one honest held-out eval.

---
## FATAL

**F1. The "real WhatsApp" benchmark is synthetic and leaks into training.**
- The file is `data/synthetic/real_benchmark_starter.jsonl`. It was committed in 627e025 ("synthetic Hinglish order generator") in the same minute as the generator.
- RESULTS.md:9 calls it "hand-collected, non-synthetic … `data/private/real_test.jsonl`".
- Overlap script: **43/50 "real" texts appear verbatim in train.jsonl and in tinker_sft_train.jsonl**.
- Synthetic test: **277/320 test rows appear verbatim in train**. Train has only 353 unique texts out of 1,280 rows.
- So every "100.0% (50/50)" in README, RESULTS and post (30 iterations of them) measures memorisation.
- Fix: dedupe by normalised text. Rebuild train and test with templates split by family (no template shared across the split). Collect 50 or more genuinely real anonymised messages into `data/private/`. Re-run one baseline and one fine-tune. Report whatever comes out, even 70%. Time: 6–8h plus collecting real data.

**F2. The gold labels are wrong: "aaj/tonight" is labelled `date: tomorrow`.**
- 197 train and test rows that contain aaj, today or tonight are gold-labelled tomorrow, e.g. "cancel dinner today" and "change 1 to 2 thalis for dinner tonight".
- All 320 test rows are `tomorrow`.
- A model that scores 100% on these labels has learned the bug.
- Fix: correct the generator, add a `today` class, regenerate. Time: 1–2h.

**F3. The Tinker category claim is false.**
- post.md:178 says a LoRA "trained … on Thinking Machines' Tinker platform", model `qwen2.5-3b-tiffintally-lora`.
- Reality:
  - All fine-tuning is Modal A10G on **Qwen2.5-0.5B** (`scripts/modal_finetune.py`, RESULTS §2).
  - There's no `tinker` SDK in pyproject.toml.
  - `extract/tinker.py:27,83` POSTs to an invented OpenAI-style `https://api.thinkingmachines.ai/v1/chat/completions`.
  - With no key, it returns the regex heuristic labelled `-surrogate` (tinker.py:56-80).
- Modal isn't a challenge partner.
- Fix: actually run SFT with the Tinker SDK (the promo credits were in the plan) on a deduped set, or drop the Tinker category. Time: 4–6h, or 5 min to drop it.

**F4. The TabPFN result isn't TabPFN.**
- RESULTS.md:199 itself says "TabPFN Regression (**HistGradientBoosting-Fallback**) 0.79".
- post.md:153,179 present 0.79 MAE as TabPFN, "a record", "eliminating ₹4,200/month".
- `data/kitchen_history.csv` is synthetic (`scripts/gen_history.py`, seeded random). Also, the CSV starts 2026-07-01 while the generator default is 07-15, so the committed CSV isn't reproduced by the script as written.
- The ₹4,218/month savings and "18x ROI" are derived from that synthetic number.
- The TabPFN client licence is non-commercial, and the post never says so (a ₹249 paid product).
- Fix: run it with a real `TABPFN_API_KEY` and save the run JSON. Label the data "synthetic, illustrative". Delete the rupee-savings claims or mark them as assumptions. Add a licence note. Time: 1–2h.

**F5. The "edge benchmark" is faked.**
- `tiffintally/edge.py:120-125` sleeps, then emits `spec.target_latency_ms * (0.95..1.05)`. The latencies, RAM (`450.0 + adapter`) and "100% EM" are all constants from `TIER_CATALOG`.
- `tiffintally benchmark-edge` prints "292.7 ms … 100.0%" with no model loaded.
- The catalog also contradicts RESULTS:
  - edge.py:38-41 lists Tier 1 as r=4, α=16, q/v only.
  - RESULTS Part C lists Iter 30 as r=32, α=64, attn_only.
- README sells "Raspberry Pi 5 / GGUF q4_k_m" tiers that were never run on a Pi or quantised.
- Fix: delete edge.py, the CLI commands, the README tier table and the badge. Time: 30 min.

**F6. The first-user story is very likely fabricated.**
- post.md:159-172 (Mrs. Kulkarni, Karve Nagar, verbatim Hindi quotes) first appears in c4f3c1a, **Oct 13, 14:02 IST**, the bulk commit where all 10 phases landed within about 2 minutes.
- "Last Sunday" would be Oct 11, the day before the challenge opened.
- The quotes praise the KDS touch station and say "we implemented the voice transcriber" because she asked. Those features were committed on Oct 14 at 18:39.
- Unless you really did this visit, it's an invented testimonial. The spec said only you write this section.
- Fix: delete it. Do a real 20-minute session with any cook (or say honestly "no first user yet"). Time: 10 min to delete; a real session takes half a day.

**F7. Phantom customers are hardcoded into every prep sheet.**
- `app.py` `process()` passes `standing_orders={"priya":1,"rahul":1,"vikram":2,"amit":1,"sneha":1}` to `reconcile_orders` for every upload.
- Probe: 3 messages (2+1+1 thalis) gave `total_thalis = 10`. That's 6 phantom lunches.
- A real cook would over-cook for imaginary customers.
- Fix: make standing orders a per-cook setting, defaulting to empty. Time: 1h.

## MAJOR

**M1. The product never uses the fine-tuned model.**
- The app and CLI only call `GemmaExtractor` (app.py:70,163; cli.py:57).
- With no key that's `heuristic_extract` regex.
- The Qwen LoRA lives on a Modal volume and isn't served anywhere.
- The "open model is what makes it work" story is broken.
- Fix: serve one adapter (Modal web endpoint or Tinker sampling) behind a flag, or reframe honestly. Time: 3–4h.

**M2. Early eval runs are mislabelled heuristics.**
- `evals/runs/20261013_134313/summary.json`: "gemma-2-9b-it" and "qwen2.5-3b-tiffintally-lora" have **identical** metrics (0.8244 / 0.72) at **0.03 ms p50 latency**. That's the regex fallback under model names.
- `tiffintally eval` on its own errors with "Missing command".
- The README says "All benchmark tables are generated from reproducible runs in `evals/runs/`". Only 2 runs exist there, and the 30 iteration JSONs sit loose in `evals/`.
- Fix: delete those runs. Make eval refuse to label a fallback as a model, so `used_fallback` means the model name gets "-fallback" appended. Time: 1h.

**M3. Parser drops and merges real orders.**
- Probe input → result:
  - "kal 1 lunch, mera roommate **left** for home" was flagged `is_system=True`, because the `SYSTEM_PATTERNS` substring "left" (parser.py:40-41) also matches "removed".
  - Lines in `13.10.26, 22:17 - Neha: …` and `2026-10-13 22:18 - …` formats were **glued into the previous message**, so 2 orders were lost silently.
  - An unparseable date falls back to `datetime.now()` (parser.py:79) without any warning.
- Fix: anchor the system patterns to full known strings, add the dot and ISO date regexes, and flag unparsed headers. Add tests. Time: 2h.

**M4. Date semantics are wrong in the reconciler and the heuristic.**
- "aaj raat 1 dinner" was extracted as `tomorrow`.
- reconcile.py:118-124 also lets both "today" and "tomorrow" events through for any target.
- "kal" isn't resolved against the message's own timestamp, so a message sent at 00:30 is off by a day.
- Fix: resolve relative dates to absolute dates using the message timestamp, then filter. Time: 2–3h.

**M5. Global in-memory state means cross-user data leaks once deployed.**
- `CURRENT_SHEET`/`CURRENT_EVENTS` are module globals (app.py:35-41).
- On Render, any visitor sees the last cook's customer names, orders and dues.
- This contradicts the privacy pitch.
- Fix: keep demo mode synthetic only, with a per-session id (cookie) or no persistence. Time: 1–2h.

**M6. Committed "real" data with full names.**
- real_benchmark_starter.jsonl has "Ravi Teja", "Priya Singh" etc. in `data/synthetic/`.
- If it's real, that's PII in git history. If it's synthetic, it's mislabelled as real (F1).
- Fix: either way, rename it to synthetic or purge it. Time: 15 min (purging history takes longer).

**M7. Pseudonymisation claim is overstated.**
- README: "names mapped to C001.. in local SQLite … phone numbers never leave".
- The Gemma API key is sent in the URL query string (gemma.py:88-89), so it appears in logs and tracebacks.
- Sentry is initialised in tests and actually tries to send events ("Sentry is attempting to send 3 pending events" at the end of pytest).
- Check what is in Sentry spans: raw text may be shipped.
- Fix: use the `x-goog-api-key` header, scrub Sentry breadcrumbs, and add `send_default_pii=False` plus a test. Time: 1h.

**M8. Partner claims that aren't real yet.**
- `.tech`: post.md:183 links https://tiffintally.tech, and curl returned no response (000, unresolved).
- Render: "containerized" (post.md:180), but there's no Dockerfile and there's no evidence of a deploy.
- Sentry ($100) and the voice transcriber run on a canned fallback: `transcribe.py:108-118` returns a hardcoded sentence based on the **filename** ("cancel" → "Aunty kal lunch cancel…").
- Gemma: default `gemma-2-9b-it` on AI Studio. Check it's still served (Gemma 3 is current); no real Gemma run is saved.
- Fix: claim only the categories with saved proof (screenshots, run JSON). Delete the filename-keyed transcript or label it "demo stub". Time: 1–3h, depending on how much you deploy.

**M9. The writing reads as AI slop and over-claims.**
- "Certified Production Model Tiers", "Grand Champion", "Pathology 13", "All-Time Record 295.7 ms", "18x ROI", 13 numbered features, 7 badges, a 2,377-word post, a "30-iteration research arc" for 0.01 changes in loss on memorised data.
- Ten feature commits landed within 2 minutes (b440903→c4f3c1a), and 6 more within 30 seconds on Oct 14 at 18:39. That's an obvious agent dump.
- Writing quality is weighted most heavily in judging.
- Fix: rewrite to about 1,000 words. Lead with one cook's 10 PM problem, show one real failure table, have one "what didn't work" section, and cut KDS/BOM/edge/active learning. Time: 3–4h.

**M10. Idea and market weaknesses that aren't addressed.**
- Most cooks with 30–50 customers already manage with a notebook or a Google Form or poll. The pitch never compares against "send a fixed-format order template", which is free.
- ₹249 a month isn't evidenced. The only "will pay" quote is the fabricated one in F6.
- Exporting a WhatsApp chat every night is friction the cook has to do by hand, and that's the real adoption risk.
- ElevenLabs reading out a brief is gimmicky for a cook who can glance at a sheet.
- TabPFN on 90 synthetic days demonstrates nothing.
- The honest pitch: messy-chat-to-prep-sheet, with dues, plus a privacy and cost reason for using a small open model.
- Fix: add a "why not a Google Form" paragraph and the export-friction limitation. Make TTS optional. Time: 1h.

## MINOR
- **m1.** README badge says Python 3.12, while render.yaml pins 3.11.17 and pyproject allows `<3.13`.
- **m2.** Synthetic test is 320 rows, but the modal evals report `num_samples: 30` (iter_30.json). The subset isn't explained.
- **m3.** "71 automated test suites" in the README means 71 tests. The "Test Suite: 71 passed" badge is static.
- **m4.** CI was red on 81c6c98 and green on a3241cf. Fine, but the badge was shown before CI was green.
- **m5.** Broad `except Exception` swallows errors in gemma.py:161, tinker.py:142, telemetry.py (5x), feedback.py:67 and app.py:170, all falling back silently to regex. Surface `used_fallback` in the UI.
- **m6.** Deprecation warning: starlette TestClient with httpx.
- **m7.** `evals/telemetry.jsonl` and `hf26-w2-sidehustle/` (my planning pack, including the agent prompts) are committed into the repo. Remove the pack, or credit it as planning docs.
- **m8.** Prompt-injection "guardrail" is a regex that strips `<|im_start|>`. It's fine, but calling it "Adversarial … Defense" oversells it.

## Not found (checked)
- No API keys in git history. I grepped all diffs for AIza, sk-, hf_, Sentry DSN and literal keys. gitleaks isn't installed, so run it before submitting.
- `.env` is gitignored.
- All commits are on Oct 13–14 IST, inside the window.
- MIT licence is present. CI exists (ruff and pytest).

## Priority plan (about 2 days)
1. **Day 1 AM:** F6 (delete the user story), F5 (delete edge), F7, M2, M6. That's about 3h.
2. **Day 1 PM:** F1 + F2: fix the labels, dedupe, split by template, collect real messages. About 8h.
3. **Day 2 AM:**
   - Run the honest evals: Gemma baseline with a real key, plus the fine-tune. Use Tinker for real (F3) or drop it.
   - Run real TabPFN or drop the category (F4).
4. **Day 2 PM:**
   - Fix M3, M4 and M5.
   - Deploy to Render with demo data only (or drop the claim). Fix DNS for .tech or drop it.
   - Rewrite the post (M9, M10).
   - Run gitleaks.
