# TiffinTally re-audit #3: Vedant817/tiffintally @ aaa3790

Reviewed Fri 16 Oct 2026, 3:00 to 4:00 PM IST. Previous reviews: REDTEAM.md (a3241cf), REDTEAM2.md (32aecc0). Fresh clone: `/workspace/tt3`. Probe scripts and raw output: `/workspace/tt-audit3/probes/`.

**Time left:** about 68 h 30 m to the deadline, Mon 19 Oct 2026 12:29 PM IST (= Sun 18 Oct 11:59 PM PDT). Recommended publish time: **Sun 18 Oct by 9:00 PM IST**. That leaves 15 h of buffer for a DEV editor, deploy or video problem.

Everything below is something I ran or read in the repo unless it carries an **[unverified]** label. Win-odds numbers are my own estimates, not published figures.

---

## 1. Verdict

The honest-engineering turnaround is real. Since REDTEAM2 the team fixed most of the extractor and ledger bugs, closed the path traversal, XSS and shared-state holes, froze the test split, stopped the eval from overwriting RESULTS.md and moved the self-reviews out of the root. But the entry is still **not submittable**. There is no DEV post that matches the code, no live URL, no video, CI has been red for three pushes in a row with no jobs running at all, and the "open model at the core" is a Qwen2.5-3B adapter whose licence forbids commercial use, served from a public unauthenticated GPU endpoint that took 40 s on a cold call (the app gives up after 20 s) and, on the demo sample a judge will click, loses a customer and a ₹1,500 payment silently. The newest commits also made the docs lie in the other direction: README, RESULTS, post.md, the page footer and DEPLOY all still say "adapter not served / no key means nothing leaves the machine", which the default config now contradicts.

All of it is fixable in about 20 to 24 focused hours. The best realistic outcome is the overall prize with a small chance (my estimate: 3 to 6 percent) plus one or two partner categories (Gemma, Render or .tech, if genuinely used and shown). If the three blockers (CI, post, live demo or video) are not fixed, the odds are about zero, because a post that is missing, off-template or untagged is simply not a valid entry.

## 2. Scorecard (my estimates, 0 to 10)

| Dimension | Score | Why |
|---|---:|---|
| Idea and fit to theme | 6.0 | Real, specific niche; the pain is real. Crowded space, and free or cheap structured alternatives exist (section 8). |
| Technical correctness | 5.5 | Parser, reconciler and ledger are much better (probe: 40/48 adversarial extraction cases pass, ledger arithmetic right). Live model path and the Gemini path are broken (T3-007, T3-008). |
| Open-model core | 3.0 | A served model exists, but the licence, reliability, access control and "open" reproducibility (adapter lives on a private Modal volume) are all weak. |
| Honesty and claims hygiene | 4.0 | Retractions are creditable. But three different numbers for one adapter, and docs that contradict the code. |
| Submission readiness | 1.5 | No post, no link, no video, CI red, no partner category provable. |
| Business case | 3.5 | No price, no unit cost, no real user; competitors are cheaper or free. |
| **Overall readiness today** | **3 / 10** | Reachable to about 6.5 with the plan below. |

## 3. What changed since the last review

Seven commits landed on Fri 16 Oct between 14:52:47 and 14:53:10 IST (23 seconds apart, a batched push), on top of the 15 Oct round-2 fixes (db6bdc6 and earlier):

- `e8da512`..`aaa3790`. In short: Modal-served extractor (`scripts/modal_serve.py`), the app calls it by default (`extract/gemma.py`), eval measures regex vs served model, a head-to-head script and charted dashboard, the superseded runs moved to `evals/retracted/` with an explanation, and `evals/telemetry.jsonl` untracked.
- Test-count: 186 tests (was 104). `ruff check` and `ruff format --check`: clean.
- Not changed: README, RESULTS.md, post.md, DEPLOY.md, `render.yaml`, `.env.example`, `ci.yml`, `docs/demo-script.md`, `index.html` footer.

## 4. Status of the earlier findings

| ID | Finding (short) | Status | Evidence |
|---|---|---|---|
| R2-F1 | No open model in the product | **Partly** | Default backend is now Modal (`gemma.py:47`, `EXTRACTOR_BACKEND` defaults to `modal`), live call returned the Qwen2.5-3B+LoRA reply. But see T3-004 to T3-008. |
| R2-F2 | No deploy or video | **Open** | `tiffintally.onrender.com` serves someone else's Next.js app; `tiffintally.tech` no response (curl 000). |
| R2-F3 | Post off-template, wrong tags | **Open** (and PROGRESS.md wrongly says "done") | `post.md:1-5`: `published: false`, tags `hacktoberfest, python, machinelearning`. |
| R2-F4 | eval overwrites RESULTS.md | **Fixed** | `tiffintally eval` ran twice; `git diff -- RESULTS.md` empty; CI job exists but cannot run (T3-001). |
| R2-F5 | Complaints, pauses, times become orders | **Mostly fixed** | Probe 3: 40/48 pass. Remaining failures in T3-016. |
| R2-F6 | Ledger double-bills, bills cancelled meals | **Fixed** | Ledger now bills final state: Asha 3 thalis ₹240, Ravi cancel ₹0. Residual issues T3-013. |
| R2-M1 | Model failure silent and mislabelled | **Partly** | Per-message counts exist and stop-on-terminal-error works. Banner still names Gemma when only regex ran (T3-011). Silent drop when the model returns fewer rows than messages (T3-007). |
| R2-M2 | Late cancels ignored | **Fixed, with a bug** | Surfaced with an "Accept" button; total is off by one per late cancel (T3-014). |
| R2-M3 | Post-midnight "kal" | **Fixed** | Goes to review/late. |
| R2-M4 | Order dependence | **Fixed** | Shuffle seeds 0 to 3 now give identical results (line_index tie-break). |
| R2-M5 | "ek aur" overwrites; cook counted | **Fixed** | "ek aur" gives 3; cook name setting exists (default empty, so default is still 5 for the group sample, T3-015). |
| R2-M6 | US/IN date ambiguity | **Open** | `10/12/26, 8:00 PM` still parsed as 10 Dec, no warning (probe e2e). |
| R2-M7 | Path traversal | **Fixed** | `traversal_probe.ogg` not created; uuid names. |
| R2-M8 | Global corrections / SFT export | **Fixed** | Per-session files `corrections_<sid8>.jsonl`. |
| R2-M9 | Voice cache by date | **Fixed** | `VoiceBriefService(session_id=...)`. |
| R2-M10 | Weak pseudonymisation | **Mostly fixed** | Payload probe: names, spaced phone and flat masked. Side effects T3-012. |
| R2-M11 | No upload limits | **Mostly fixed** | 21.6 MB gets 413 in 0.0 s; zip accepted; UTF-16 decoded. Sessions still unbounded for 2 h (T3-019). |
| R2-M12 | Test-set tuning | **Fixed, then broken on Linux** | Hash frozen, dev split added; hash tests fail on Linux (T3-001). |
| R2-M13 | Forecast worse than nothing | **Fixed** | Deleted. Dead schema fields and the `tabpfn-client` dependency remain (T3-021). |
| R2-M14 | Post is an apology | **Open** | post.md unchanged. |
| R2-M15 | No first user | **Open** | Needs a human. |
| R2-m1 | Ledger XSS | **Fixed** | `onclick="copyReminder(this)"`, data attribute. |
| R2-m2 | Planning files in root | **Fixed** | Moved to `docs/planning`, `docs/review`. |
| R2-m3 | Tracked telemetry | **Fixed** | Untracked, gitignored. |
| R2-m4 | PROGRESS.md stale | **Fixed** (new stale entries: F3 "done") | |
| R2-m5 | >500 chars truncated | **Open** | 697-char message: trailing "kal lunch 5" not on the sheet. |
| R2-m7 | Free-text date box | **Open, worse** | `2026-02-30` returns HTTP 500 (ValueError, `dates.py:46`) (T3-017). |
| R2-m8, m9, m10, m12 | /health, eval default, export-edge | **Fixed** (warning remains) | |
| R2-m11 | Render build verification | **Partly** | Render supports uv since 2025-06-12 (Render changelog). Config still has problems (T3-018). |
| — | Secrets | **Clean** | gitleaks 8.21.2: 101 commits, no leaks; regex scan of all history found only `xi-api-key` header name; phones in history are the 98765 43210 placeholder style. |

## 5. New findings

Severity: **BLOCKER** = entry invalid or demo cannot work. **CRITICAL** = judge-visible failure, or a security or honesty problem. **MAJOR** = real defect. **MINOR** = polish.

### BLOCKER

**T3-001. CI is red and runs zero jobs; a second failure sits behind the first.** GitHub public API: runs for `62cb47f`, `db6bdc6`, `aaa3790` all `completed/failure` with 0 jobs (`/actions/runs/38880206979/jobs` returns `total_count: 0`); last green was `32aecc0`. Cause 1: `.github/workflows/ci.yml:54` starts a step name with a backtick; `yaml.safe_load` raises `ScannerError ... found character '`'` at line 54 col 15. Cause 2 (hidden behind it): `tests/test_split_frozen.py` hashes `test.jsonl` and `dev.jsonl` as stored. On Linux the bytes are LF; the frozen hashes were recorded from a Windows CRLF checkout (LF sha `6e9f49ed...`, CRLF sha `1d7926f8...` matches `split_report.json`). Two tests fail (`2 failed, 184 passed`). Cause 3: the `no-results-drift` job runs `tiffintally eval` with the default backend, which calls the live Modal endpoint for every row: it took **7 min 12 s** here and costs GPU time on each push.
Fix: quote the step name; canonicalise line endings before hashing (keep the recorded hashes, do not re-freeze); set `EXTRACTOR_BACKEND=off` for the CI eval step. I verified that the existing patch `/workspace/tiffintally-ci-fix.patch` applies cleanly to aaa3790 and, with it, ruff, format, and 186 tests pass and `eval` leaves RESULTS.md untouched. Effort: 20 min.

**T3-002. No live deployment, no video, and the obvious Render URL belongs to someone else.** `https://tiffintally.onrender.com/` returns 200 and is a **different** product: a Next.js app titled "TiffinTally · More cooking. Less chasing." (WhatsApp Linked-Devices QR, "Set up workspace"); `/health` returns 404 after 9.7 s. `https://tiffintally.tech` does not connect. Render service names are global, so `name: tiffintally` in `render.yaml` will get a suffixed URL, and any hard-coded `tiffintally.onrender.com` in the post would point at a competitor. Nothing in the repo is deployed; the video script (`docs/demo-script.md`) describes features that were deleted (forecast card, confidence interval).
Fix: deploy under a unique name, use the URL Render actually prints, add the Render free-tier cold-start note to the post (service sleeps after inactivity **[unverified today; check Render docs]**), record a 60 to 90 s video that matches the current UI. Human steps in section 10. Effort: 2 to 3 h plus human time.

**T3-003. There is no valid DEV post.** `post.md` has `published: false`, tags `hacktoberfest, python, machinelearning` (required: `devchallenge`, `hf26challenge` via the template), no "This is a submission for ..." line, no Prize Categories section, no demo, no repo link, and it states things that are now false ("Neither adapter is wired into this app"; the page "says rules fallback" when no key is set, but the default now calls the Modal model). It is also a confession essay (about half the text is retractions) when Writing Quality is the heaviest-weighted criterion. Fresh template headings from live DEV entries (Oct 13 to 15): `## What I Built`, `## Demo`, `## Code`, `## How I Built It`, `## Prize Categories`; the official template button was not readable by me, so use the button, not a copy.
Fix: rewrite from scratch on the DEV template (FIX_PROMPT3 Phase 8). Effort: 3 h.

### CRITICAL

**T3-004. The open model is non-commercial and the code says otherwise.** `scripts/modal_serve.py:9` says "Qwen2.5-3B-Instruct (Apache-2.0 weights)". Hugging Face's API for `Qwen/Qwen2.5-3B-Instruct` returns `license: other`, `license_name: qwen-research`, and the licence text says "FOR NON-COMMERCIAL PURPOSES ONLY" and "If you are commercially using the Materials, you shall request a license" plus a "Built with Qwen" notice duty for derived models. (`Qwen/Qwen2.5-1.5B-Instruct` is `apache-2.0`.) The theme is "something someone would actually pay for", so a paid product on non-commercial weights undermines the pitch, and the false Apache line is a factual error in a public repo. Also: the LoRA adapter is not published anywhere a judge can fetch (private Modal volume), so "open" and "reproducible" are claims without an artifact; `scripts/modal_finetune.py` can retrain but the README gives no steps.
Fix: make a Gemma 4 model (Apache-2.0 weights per Google; hosted on the Gemini API) the primary extractor, keep the Qwen LoRA as a documented experiment under its real licence, fix the docstring, add the "Built with Qwen" line wherever the adapter is described. Optionally retrain on an Apache-licensed base if time allows. Effort: 3 to 5 h (D1 in section 9).

**T3-005. The live path is unreliable by construction.** Measured: first call to the endpoint after idle took **39.98 s** (cold, `/` returned 404 in 4.4 s then POST 40 s); warm calls 10 to 12 s for 5 messages and 12.8 s for the 10-message demo sample (probe live_modal, probe sample live). `gemma.py:53` sets `REQUEST_TIMEOUT=20`, 3 attempts, so a cold start fails all three tries (~62 s) and every batch of 40 messages re-does that: a 200-message paste could run for minutes, past the free web service's request limit **[unverified]**, and the fallback then silently produces regex output (labelled as Gemma, T3-011). `scaledown_window=300` means the demo is cold whenever a judge arrives after five idle minutes. Model weights are also reloaded inside `extract_batch` on every call (no `@modal.enter`), which is why a 5-message call takes ~10 s.
Fix: do not make the demo depend on a cold GPU: Gemma via the Gemini API as default (one HTTP call, seconds), Modal opt-in; if Modal stays, load the model once per container (`@app.cls` + `@modal.enter`) and set `min_containers=1` only for the judging window if credits allow. Effort: part of D1.

**T3-006. Public, unauthenticated GPU endpoint.** The URL is hard-coded in `gemma.py:35-38`, `scripts/head_to_head.py:140` and the committed eval JSON. I sent one synthetic message with no credentials and got a full inference (HTTP 200, A10 GPU) (probe live_modal; my handful of test calls plus one 50-row eval used a small amount of his Modal credit, noted for transparency). Anyone who reads the repo can burn his GPU credits or the account's quota, and the endpoint has `docs=True`. It also receives customer text (pseudonymised) from every deployed instance.
Fix: bearer token in `modal_serve.py` (Modal secret) checked on every call; app sends it from env; remove the URL default from code (env only); redeploy under a new name or stop the old app (`modal app stop`); scrub the URL from docs where possible (it stays in git history). Effort: 45 min plus a human redeploy.

**T3-007. The default model path gets the demo sample wrong and is less safe than the regex.** On the page's own "Load sample chat" (10 messages), with the live model: Karan's "...roommate Tanvi ke liye bhi ek lunch add kar dena" gives **only Karan** (Tanvi silently dropped), Vikram's "₹1500 GPay kiya" gives a payment with **no amount** (his ledger shows ₹0 paid instead of ₹1,500), Priya's mod becomes "roti nahi rice". Lunch total 6; the correct total is 7 (Ravi 2, Priya 1, Karan 1, Tanvi 1, Pooja 2). The regex path also gives 6, but it drops Priya with a visible review flag, whereas the model drops Tanvi with none. Separately: "kal lunch bahut teekha tha" (feedback) came back from the real model as `new lunch x1`, and "₹500 GPay kiya" as payment amount None. There is no rules-based validation of model output, and when the endpoint returns fewer rows than messages, `zip(rows, sent, source)` (`gemma.py:157`) truncates silently (probe: 3 messages, 1 row returned: two customers vanish, no flag). A "garbage" model reply (strings instead of objects) is counted as `model_messages=3`.
Fix: a guard layer after every model reply: reject or review on row-count mismatch, take payment amounts from the regex when the model omits them, send feedback and complaint messages to review, flag when the regex and the model disagree on action or quantity. Effort: 3 h (Phase 3).

**T3-008. The Gemini/AI Studio path emits N times too many events.** With a fake Gemini-format server and 3 messages, `extract_batch_counted` returns **9 events** (each message re-parses the whole batch reply; `gemma.py:167-176`). The sheet hides it only because identical new-orders collapse; an "add" ("ek aur") or a payment is multiplied. This matters because the Gemma path is exactly the fallback the team will reach for when Modal is cold.
Fix: ask for an indexed result (`{"results":[{"i":0,"events":[...]}]}`) and match by index, with a missing-index fallback. Effort: 1.5 h with tests (probe3_gemini_path.py is a ready regression harness).

**T3-009. Docs and UI now contradict the code (honesty).** The earlier honesty work made the repo credible; the 16 Oct commits flipped behaviour without updating the claims.
- `README.md:25-27` "The app does not serve the adapter ... With no Gemma key it still uses the rules parser"; `RESULTS.md` last line "The FastAPI app does not load this adapter"; `post.md` "Neither adapter is wired into this app". Default backend is `modal`, so false.
- `tiffintally/templates/index.html` footer: "A hosted model is called only when its API key is set ... With no key, no chat text is sent." **False in the default config**: pseudonymised text goes to the Modal endpoint with no key (probe: payload captured, `T3-012`).
- README quickstart lists `tiffintally forecast` (command removed: "No such command 'forecast'"); `RESULTS.md` lists `scripts/gen_history.py` (does not exist) and `data/kitchen_history.csv` is gone.
- `docs/demo-script.md` demos a forecast card and TabPFN disclaimers for a feature that was deleted; `docs/DEPLOY.md` and `.env.example` and `render.yaml` still say `gemma-2-9b-it` (no longer served).
- `PROGRESS.md` marks F1 "done" and F3 "done", but the post is not written, and F2 says "awaiting deploy".
Fix: one honesty sweep, driven by a claims table (Phase 7). Effort: 2 h.

**T3-010. The headline accuracy numbers do not agree, and the lead is one template.**
- Same adapter, same frozen test, three figures: **84.0%** (README/RESULTS, includes `date` in the match, older test file), **88.0%** (dashboard, `head_to_head.json`), **90.0%** (`evals/runs/20261015_174336`; I re-ran `tiffintally eval` today and got **90.0%** again). Definitions differ (run 31 includes `date`; the others score meal, qty, action, mods), and 88 vs 90 comes from different batching, but the repo never says so in one place.
- The "+10 points over regex" is carried by one synthetic template. `bina mirchi ke N dabba dinner` is **6 of the 50 test rows** (12%); in `head_to_head.json` 6 of the model's 11 wins are those rows, because the regex's mod label for them is "less spicy" while the gold label is "no chili", a label-convention mismatch, not understanding. Excluding that template: regex **39/44 = 88.6%**, model **38/44 = 86.4%**. The regex wins.
- The strongest honest result is the control: base Qwen2.5-3B without the adapter scores 66.0%, with adapter 88.0% (`base_model_no_adapter` in the artifact), so fine-tuning helps that model on this synthetic task. That is worth leading with, with the caveat that the test set is synthetic and from the same generator as train.
- `evals/dashboard.html:64-65` publishes local paths `C:/Users/vedan/Documents/Resources/Code/tiffin-tally/...`.
Fix: one definition of exact match, one table per (model, split), a per-template breakdown, the "excluding one template" line, and no local paths. Effort: 1.5 h (Phase 4).

**T3-011. The banner names a Gemma model that did not run.** With the backend off or Modal unreachable, the sheet says "Regex fallback: 0 message(s) read by **gemma-4-26b-a4b-it**, 10 read by the on-device rules" (probe sample off; `prep_sheet.html:18-20`, label from `extractor.model_name`). A judge reads that as Gemma being configured. If the post claims Best Use of Gemma, an honest check of the live site could show Gemma never ran. Also `render.yaml` still sets `GEMMA_MODEL=gemma-2-9b-it`.
Fix: label comes only from a response (`served_model`); fallback says "rules (regex)" with no model id. Effort: 30 min.

### MAJOR

**T3-012. Privacy claims vs behaviour.** (a) T3-009: footer says nothing is sent without a key; default sends text to a personal endpoint. (b) The token map is one global SQLite file (`data/privacy_map.db`, `DEFAULT_DB_PATH`) shared by every session; the extractor builds `Pseudonymizer()` with no session. Probe: a mock model that answered with token `C001` produced the customer name "Neha" from an earlier test run, i.e. a wrong or mismatched token resolves to another cook's customer. (c) Masking glues tokens: `"call 98765 43210"` became `callC020` (the space is eaten), which also changes the text the model sees. (d) If Gemma goes through the free AI Studio tier, a third-party summary of Google's terms says prompts may be used to improve Google products and EEA/UK/Swiss apps need paid services **[unverified; check ai.google.dev terms]**; the post must say this next to any "your data stays private" claim.
Fix: per-session in-memory map, token boundary spacing, sentence in the post. Effort: 1.5 h.

**T3-013. The "dues ledger" is a one-paste calculator.**
- Price is hard-coded: `app.py:329` `price_per_thali=80.0`; no UI to set price per meal, no menu, no monthly plan.
- Money is `float`. The reminder truncates paise: `reconcile.py:547` `int(entry.balance_due)`. Probe: Ravi paid ₹99.99 against an ₹80 bill: ledger shows paid ₹99 and balance **₹-19** (true -19.99).
- No carry-forward: `previous_balances=None`, sessions are process memory, restart or two-hour idle loses everything. A cook cannot track a month.
- Sheet and ledger disagree for a late cancel: Asha's "kal lunch cancel" at 23:30 leaves her lunch **on the prep sheet** (cutoff 22:00, cook still cooks) but the ledger bills her **₹0**.
Fix: price field with a default, `Decimal`, paise-safe reminders, CSV export/import of balances (works without a database), consistent policy for late cancels shown on the sheet. Effort: 3 h.

**T3-014. "Plates you no longer need" is off by one per late cancel.** `reconcile.py:418-421` starts `pending` at the number of late cancels and then adds each cancel's quantity. A 2-plate late cancel prints "3 plate(s) you no longer need" (probe: `late cancel: 2 3`; two customers: still 3). Fix: drop the `sum(1 ...)`. Effort: 10 min plus a test.

**T3-015. Re-stating an order empties the sheet.** `kal lunch 2` then `kal lunch 3 kar do` ten minutes later gives **lunch 0** and both rows land in review flagged `same_minute_conflict` (probe: also for "kal lunch 3 hi bhejna", "actually kal lunch 3 chahiye", "make it 3 for kal lunch"). Only an explicit "change" keyword works. Customers re-state orders constantly. The flag name is also wrong (they were not in the same minute). Default group chats also count the cook's own confirmations as a customer (5 instead of 3) unless the cook types her name in the optional field. Fix: latest message wins when timestamps differ (show "was 2, now 3"), conflict only for the same minute, and auto-suggest the cook name (most frequent sender who replies "ok/done"). Effort: 2 h.

**T3-016. Residual extractor failures (regex path, 8 of 48 probe cases fail).** `kal ka lunch cancel mat karna` becomes a cancel; `kal lunch cancel nahi karna, 2 hi chahiye` becomes a cancel; `aaj ka lunch aaya nahi, paise wapas` becomes new lunch x1; `kal lunch 2 ya 3 pata nahi` becomes lunch 2 with no review; `शनिवार को लंच बंद` becomes none (no pause); `kal jevan 2` and `udya doghanche jevan` (Gujarati/Marathi roman) give none; `kal lunch 1000` is not flagged by the heuristic itself (the app path clamps to 20 and flags it, verified). A message over 500 characters loses its tail ("kal lunch 5" after 697 characters missing). Evidence: `probes/probe3_extract.out`. The generator advertises Marathi/Gujarati, the product does not handle them yet; either handle the top 10 forms or remove the claim. Effort: 3 h.

**T3-017. The date box fails ugly.** `target_date` is free text (`index.html:43`). `2026-02-30` raises `ValueError` at `dates.py:46` and returns an HTTP 500; `banana` and `16/10/2026` are accepted silently and produce an empty sheet titled with the garbage. The US/IN ambiguity (`10/12/26`) still silently reads December. Fix: `<input type="date">`, server-side validation with a friendly error, ambiguity warning in the parser. Effort: 1 h.

**T3-018. `render.yaml` and the dependency set are not ready for a free instance.** `GEMMA_MODEL` stale (`gemma-2-9b-it`); `env: python` is the old key (current spec uses `runtime`) **[unverified; check Render blueprint docs]**; start command `uv run uvicorn ...` re-syncs dev dependencies (ruff, pytest) at boot unless `--no-dev`/`--no-sync` is used; no `EXTRACTOR_BACKEND`, `EXTRACT_TIMEOUT`, token or URL variables defined, so the deployed behaviour is whatever the code defaults to; the service name is taken (T3-002). `pyproject.toml` still lists `tabpfn-client` (never imported now), `modal` (only scripts use it), `numpy` (one import in eval); the venv here is 511 MB (pyarrow 152 MB, scipy 81, pandas 45, sklearn 32) against Render's 512 MB free RAM **[unverified, check plan limits]**. `/health` reports version 0.2.0 while `pyproject.toml` says 0.1.0. Fix in Phase 6. Effort: 1 h.

**T3-019. Sessions are only capped in theory.** `MAX_SESSIONS=500` only triggers pruning of sessions idle for over two hours; 2,000 cookieless GETs left 2,002 live sessions (probe app). Add a hard cap with LRU eviction. Effort: 15 min.

### MINOR

- **T3-020.** `extract_batch` (legacy, unused) flags every event `unparsed_timestamp` because it routes through `_Msg` with no timestamp; delete it. `TinkerExtractor`, the `forecast_*` fields in `schema.py:100-101`, `telemetry.py` forecast hooks, and four overlapping dashboard scripts (`build_dashboard.py`, `build_dashboard_page.py`, `generate_dashboard_html.py`, `parse_evals.py`) are dead weight.
- **T3-021.** `evals/modal_run_iter_1..30.json` (retracted Qwen2.5-0.5B logs) still sit in the top of `evals/`, and `evals/dashboard_data.json` says `iterations: []`. A judge opening `evals/` sees 31 run files and has to read prose to learn 30 are void. Move them to `evals/retracted/`.
- **T3-022.** Commit history shows bursts (7 commits in 23 s on 16 Oct; 16 commits in one hour on 14 Oct at 18:xx; "record Iteration N metrics" every ~7 minutes on 14 Oct). It is legitimate work, but it reads as agent-batched. State AI assistance plainly in README and post (rules allow AI use).
- **T3-023.** Voice brief reads the ISO date and says "Aaj" for tomorrow's sheet (`Aaj 2026-10-17 ke liye total 9 thalis`); the voice-note stub writes a fake `sample_voice_cancel.ogg` under `data/uploads/audio/`. The "Morning Kitchen Audio Brief (ElevenLabs)" header appears with no key and no audio.
- **T3-024.** GitHub repo About is empty (no description, topics or homepage). Add a one-line description, topics, and the live URL.
- **T3-025.** Starlette TestClient `httpx` deprecation warning in test output.

## 6. Claims versus evidence

| Claim (where) | Verdict | Evidence |
|---|---|---|
| "84.0% exact match, 50 rows" (README, RESULTS) | True for run 31 under its definition (includes `date`), older test file | `evals/modal_run_iter_31.json` |
| "Served adapter beats regex by +10 points" (dashboard) | Misleading | T3-010, 6 of 50 rows are one template; excluding it the regex wins |
| "Fine-tune lifts base 66% to 88%" (dashboard) | **Supported** (synthetic only) | `head_to_head.json: base_model_no_adapter` |
| "Apache-2.0 weights" (`modal_serve.py:9`) | **False** for Qwen2.5-3B | HF API: `qwen-research`, non-commercial |
| "With no key, no chat text is sent" (index footer) | **False** by default | payload capture |
| "Names and phone numbers masked before a hosted call" | Mostly true | payload probe; caveat T3-012 |
| "Does not serve the adapter" (README, RESULTS, post) | **False** now | default backend modal |
| "Open model at the core" (rules) | Contested | needs T3-004, T3-005, T3-006 |
| "No credit card" | Not violated by any file I read | ADR 001 |
| Real vs synthetic labelling | Good | all data `synthetic`, `real_test.jsonl` refused without provenance marker |
| "No secrets" | **True** | gitleaks clean, 101 commits |

## 7. Submission readiness against the rules

| Required element | State |
|---|---|
| New repo, started inside the window | OK. First commit `b440903`, 13 Oct 14:00 IST; challenge started 12 Oct. |
| Public repo, OSI licence | OK. Public, MIT. Description/topics empty. |
| Published DEV post on the Side Hustle template, tags `#devchallenge #hf26challenge` | **Missing** (T3-003) |
| Open-weight model or open-source AI as a core part | Contested (T3-004 to T3-008) |
| Deployed link or video demo | **Missing** (T3-002) |
| Prize Categories section listing only categories genuinely used, with proof | **None provable today** |
| Credit prior work, note post-deadline commits in README | Not yet written |
| Team handles | Solo |
| Agent session (optional, DevRelay) | Not present; optional |
| First user (bonus) | None |

**Partner categories, honestly:** Gemma becomes claimable only if a Gemma 4 model really answers in the live demo and a saved run proves it. Render needs a live service. .tech needs the app reachable on a `.tech` domain claimed through hacktoberfest.com/my/promos (auto-renew off, it renews at $29.99/yr). TabPFN, Tinker, Sentry, ElevenLabs: no proof; do not claim. GitHub Copilot: only if CI is green and Copilot's use is shown; skip.

## 8. Views

**Judge.** Writing Quality leads, and there is nothing to read. Technical Execution is a mix of careful work (frozen splits, retractions, per-message accounting) and a demo that fails on its own sample. Relevance: "open at the core" is contestable; "would someone pay" has no price or user. A judge who opens the live site (there is none) or clicks the sample (6 vs 7) loses confidence fast. Rival posts already up: ScheduleUp (WhatsApp commitments to tasks, Gemma via OpenRouter, Mastra, Temporal, Render, .tech, public demo at scheduleup.tech, seven categories) is the closest in shape and further along on presentation.

**User (a real tiffin cook in India).** The workflow is: export a WhatsApp chat every night, upload to a browser, read a table. For 30 one-to-one chats that is 30 exports, so it only works if orders arrive in one group, which the post never says. She would have to trust a count, and the first thing she needs (set my price, carry yesterday's dues, tell me what changed since last night) is missing. Devanagari and regional Roman spellings partly fail (T3-016). Positive: copy-only reminders (no auto-send) are the right policy, and review flags are visible.

**Technical.** Strong: parser, deterministic reconciler, ledger arithmetic, guard rails, frozen splits, and a real ablation. Weak: the model integration (T3-005 to T3-008), the batching and cold start, the state model (process memory, sessions), and CI.

**Business.** No price in the repo (₹80 per thali is a hard-coded constant, not a business model). Competitors: TiffinFlow (menu-link subscriber app with a free page), Tezzu (from ₹999/month plus ₹10 per order, WhatsApp broadcasts and dashboard), ElfClick (AI that runs the WhatsApp conversation, free 30-day trial), WAStore (free menu link), Rekart (full meal-plan platform) (vendor pages, retrieved today). A paste-an-export tool that costs a cook a nightly chore, against structured tools that remove the chat entirely, needs a sharper reason: **works with the chat she already has, no customer behaviour change, private, cheap**. Unit economics have no number: `Cost /1k msgs` reads "not metered here" in every report. WhatsApp reality: manual export is within WhatsApp's terms; the Business API route needs Meta approval and per-conversation fees; "link your phone by QR" tools (the other TiffinTally's approach) rely on unofficial clients **[policy detail unverified]**. Legal and policy risk for this repo is low because the cook exports her own chat and nothing is sent.

**Competitor within the challenge.** Expect many "WhatsApp to structured data" posts. The differentiators that can be proven in 48 hours: a Hinglish/Devanagari eval with failure cases, an honest "model vs rules" table including where rules win, and a working live demo with a sample chat.

**Realistic win odds (my estimates, not published):** overall prize about 3 to 6 percent after the plan; about 1 percent or less today. One partner category (Gemma or Render or .tech) about 8 to 15 percent each if genuinely used and shown. If the post, demo and CI are missing on Monday: zero.

## 9. Decision points and the recommended answers

**D1. Which model sits at the core?** Recommended: **Gemma 4 26B-A4B (`gemma-4-26b-a4b-it`) on the Gemini API as the default extractor**, with the rules as a visible fallback and the Qwen LoRA documented as an experiment. Reasons: Apache-2.0 weights per Google; commercial use is allowed; one HTTP call, no cold start or GPU bill; qualifies for Best Use of Gemma; works on Render free. Cost: one honest eval (dev and test), fix of T3-008, a guard layer (T3-007). If Gemma loses to the regex on the frozen test, say so and show the per-row reasons; the guarded hybrid is the product. Second choice (stretch): retrain the LoRA on an Apache-licensed base (Qwen2.5-1.5B-Instruct is `apache-2.0` on HF) and publish the adapter to Hugging Face.
**D2. Render or video first?** Do both. The video is the fallback that cannot fail; Render is the bonus that carries a $200 category.
**D3. First user.** One 20-minute session with any real cook or home food seller, with consent and no PII in the repo; the honest answer, even "she would not pay", is worth more than nothing. A human step.

## 10. Plan to the deadline (IST)

| When | Goal |
|---|---|
| **Now to Fri 16 Oct 11 PM** (T-61 h) | Phase 0 CI green (20 min). Phase 1 safety (token on the Modal app, remove URL default, stop old app: 45 min plus human). Phase 2 model path: indexed Gemini batching, guard layer, labels (4 h). |
| **Sat 17 Oct 9 AM to 6 PM** (T-51 to T-42 h) | Phase 3 correctness (late-cancel total, re-statement, negations, date box, ledger price and paise: 4 h). Phase 4 eval (Gemma on dev and test, honest table: 1.5 h). Human: Render deploy and .tech claim in the morning; AI Studio key. |
| **Sat 17 Oct 6 PM to 11 PM** | Phase 5 docs sweep and dependency trim (2 h). Human: ask one cook for 30 to 50 messages or a 20-minute session. |
| **Sun 18 Oct 9 AM to 3 PM** (T-27 to T-21 h) | Phase 6 deploy checks from a phone; Phase 7 video script and shots; human records the video. Feature freeze at 3 PM. |
| **Sun 18 Oct 3 PM to 9 PM** | Phase 8 post on the official template; QA checklist; publish by 9 PM. |
| **Mon 19 Oct 9 AM** (T-3.5 h) | Hard lock, no code changes. Re-check that the post is public, links work, tags show. |
| **Mon 19 Oct 12:29 PM** | Deadline. |

## 11. Human-only checklist

1. Run `modal app stop tiffintally-extract` (or redeploy with a token) so the public GPU URL stops working. Check remaining Modal credits.
2. Create a free Google AI Studio key (no card); put it only in Render env and a local `.env`.
3. Deploy on Render free (no card; stop if asked). Name must differ from `tiffintally`. Note the real URL.
4. Claim the free `.tech` domain at hacktoberfest.com/my/promos (turn auto-renew off, stop if a card is asked), point DNS at Render, confirm HTTPS.
5. Open the live URL from a phone on mobile data, twice (cold and warm). Time it.
6. Ask one real cook (or a home food seller) for consented messages or a short session. Never commit real names or numbers.
7. Record a 60 to 90 s screen video of the live site using the shot list; upload to YouTube unlisted or DEV.
8. Use the official Side Hustle template button on DEV; paste the prepared sections; set the tags `devchallenge`, `hf26challenge`; list only provable categories; list your DEV handle.
9. Add the repo About text, topics, homepage URL.
10. Optional: DevRelay session link (helps process story).
11. Publish before Sun 18 Oct 9 PM IST; re-open the published post logged out to check.

## 12. Verification log (what I ran)

| Command / action | Result |
|---|---|
| `git clone` fresh to `/workspace/tt3`; `git log` | 102 commits, head `aaa3790` (2026-10-16 14:53:10 IST), first commit 13 Oct 14:00 IST |
| GitHub public API, check-runs and actions runs for `aaa3790` | `total_count: 0`; 3 failed runs with 0 jobs |
| `yaml.safe_load(ci.yml)` | ScannerError line 54 col 15 |
| `uv sync --all-extras --dev` | ok; venv 511 MB |
| `ruff check .`, `ruff format --check .` | clean, 79 files |
| `pytest -q` | **2 failed, 184 passed** (hash tests); with the CI patch: **186 passed** |
| `tiffintally eval` (backend off) | 0.5 s, RESULTS.md unchanged |
| `tiffintally eval` (default, live Modal) | **7 min 12 s**, 90.0% model, 78.0% regex, RESULTS.md unchanged |
| `gitleaks detect` v8.21.2 | 101 commits, no leaks |
| `curl tiffintally.onrender.com/` and `/health`, `tiffintally.tech` | 200 (a different Next.js app), 404 after 9.7 s, no connection |
| Unauthenticated POST to the Modal endpoint | 200 with inference, cold 39.98 s; warm 6 to 12 s |
| Probes (all in `/workspace/tt-audit3/probes/`) | extraction table (40/48 pass), e2e reconcile and ledger, app endpoints, upload and XSS, model-output handling via a fake endpoint, Gemini-format batch duplication, demo sample on both paths |
| Hugging Face API for the Qwen2.5-3B licence | `other` / `qwen-research`, non-commercial |
| Re-fetch of the DEV launch and challenge pages | Requirements unchanged: DEV post on the template, tags, demo, open-weight core, Prize Categories section, one win per challenge |

**Not verified:** a real Render deployment (no account action taken), the Render free-tier request timeout and RAM limit, Google's current free-tier data-use terms for Gemma 4, any real-cook data, voice-note transcription with a key, ElevenLabs output.

## Appendix: file map

- `/workspace/tt-audit3/AUDIT3.md` (this file)
- `/workspace/tt-audit3/FIX_PROMPT3.md` (paste-ready prompt for the coding agent)
- `/workspace/tt-audit3/probes/` (probe scripts and raw `.out` files)
