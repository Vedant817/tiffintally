# TiffinTally: round-3 fix prompt (paste this whole file into Antigravity / OpenCode in T3 Code)

You are a careful senior engineer finishing **Vedant Mahajan's** DEV Hacktoberfest 2026 Week 2 "Side Hustle" entry **TiffinTally** (https://github.com/Vedant817/tiffintally, branch `main`, audited at `aaa3790`). Work through the phases in order. Commit after each phase. Do not stop until the Definition of Done is ticked or a `[HUMAN]` gate blocks you; at a gate, write the question to `docs/QUESTIONS.md`, keep working on everything else, and tell Vedant what you need.

## Context (verified 16 Oct 2026, 3 to 4 PM IST)
- Product: a home tiffin cook pastes or uploads a WhatsApp chat export, and gets a prep sheet (lunch and dinner counts, packing labels, mods) plus a dues ledger with copy-only Hinglish reminders. Stack: Python 3.11/3.12, uv, FastAPI, Jinja, pydantic, pytest, Render free (`render.yaml`).
- **Deadline: Sun 18 Oct 2026 11:59 PM PDT = Mon 19 Oct 12:29 PM IST.** Feature freeze Sun 18 Oct 3 PM IST. Publish the DEV post by Sun 18 Oct 9 PM IST. Hard lock Mon 19 Oct 9 AM IST: no code changes after.
- Contest requirements (re-read today from https://dev.to/challenges/hacktoberfest-week2-2026-10-12): a published DEV post on the **Side Hustle submission template**, with the tags `devchallenge` and `hf26challenge`; a brand-new project built in the window; open-weight models or open-source AI at the core; a demo; why open matters; who would pay; optional first user; a "Prize Categories" section listing only categories genuinely used; AI use is allowed; commits after the deadline must be noted in the README.
- State today: ruff clean; 184 of 186 tests pass (2 hash tests fail on Linux); **CI red with zero jobs** (`.github/workflows/ci.yml:54` invalid YAML); no deploy; no video; `post.md` is stale and off-template; the default extractor calls a public unauthenticated Modal GPU endpoint serving **Qwen2.5-3B + LoRA (Qwen Research Licence, non-commercial)**; cold start measured 40 s vs the app's 20 s timeout; the Gemini path emits N times too many events; README, RESULTS, post, page footer, DEPLOY all contradict the default behaviour.
- Read `/workspace/tt-audit3/AUDIT3.md` if you have access; its IDs (T3-001 ...) are used below. If you do not, the issues are fully described here.

## Hard rules (never violate)
1. **Never fabricate.** Every number in README, RESULTS, post, dashboard or UI must come from a command you ran, saved under `evals/runs/<YYYYMMDD_HHMM>/` and listed in `docs/NUMBERS.md` (number, file, command, date). Not run means the words `NOT RUN` and a reason. Never invent users, quotes, prices people agreed to, screenshots, traces or links.
2. **Model names come from responses only.** Never print a model id in the UI, README or post unless an API response from that model produced the result. A rules fallback is called "rules (regex)" and carries no model id.
3. **No credit card, no purchases.** If any signup or deploy asks for a card, stop that path, log it in `docs/DECISIONS.md`, take the fallback.
4. **Limited disk.** No torch, no model weights, no big downloads, never commit `.venv` or `.so` files.
5. **No secrets in git.** `.env` stays ignored. Keys only from env, only in headers. Run `gitleaks detect` before every commit.
6. **Frozen splits.** Do not edit `data/synthetic/test.jsonl` or `dev.jsonl`, their labels, or the recorded hashes in `split_report.json`. Do not tune rules against test failures; tune against `dev.jsonl` and unit tests.
7. **No real customer data in the repo.** Real messages only under `data/private/` (gitignored).
8. **No messages sent on anyone's behalf.** The app only drafts; you never send email, Slack or WhatsApp, and you never post to DEV. Publishing is [HUMAN].
9. **No history rewrite, no force-push, no deleting branches.** Add commits only.
10. **Do not touch anything outside this repo.**

## Consult protocol (when in doubt)
- Rule or requirement doubt: quote the exact sentence from the DEV challenge page, put it in `docs/QUESTIONS.md`, take the most conservative reading, and move on.
- Ambiguous product behaviour: pick the option that keeps the cook's count safe (show it for review rather than hide it), write the choice in `docs/DECISIONS.md` as a new ADR, move on.
- A fix would take more than twice its estimate: stop, write what you learned, take the smaller option listed in the phase, tell Vedant.
- Never ask the user to review code line by line. Ask only for things only they can do (accounts, keys, a cook, recording, publishing).

## Phase 0: CI green (T3-001), 30 min
1. `.github/workflows/ci.yml` line 54: quote the step name (`- name: "tiffintally eval must leave RESULTS.md untouched"`). Validate with `python -c "import yaml;yaml.safe_load(open('.github/workflows/ci.yml'))"`.
2. `tests/test_split_frozen.py`: the recorded hashes are of the CRLF form (checked out on Windows). Make the test canonicalise before hashing: read bytes, replace `\r\n` with `\n`, then `\n` with `\r\n`, hash that. Keep the frozen values in `split_report.json` exactly as they are. Add `.gitattributes` with `*.jsonl text eol=lf` so a fresh clone is stable.
3. In the `no-results-drift` job set `EXTRACTOR_BACKEND: "off"` so CI never calls a network model (it took 7 min 12 s against the live endpoint). Also set `TIFFINTALLY_TELEMETRY: "0"`.
4. Acceptance: on Linux `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` gives 186+ passed; `uv run tiffintally eval` leaves `git diff -- RESULTS.md` empty; after pushing, the Actions page shows jobs running and green. [HUMAN: confirm the green check on GitHub if you cannot see it.]

## Phase 1: Close the open GPU endpoint (T3-006), 45 min plus a human step
1. `scripts/modal_serve.py`: require `Authorization: Bearer <token>` on the endpoint, token from a Modal secret named `tiffintally-extract-token`; return 401 without it. Set `docs=False`. Load the model once per container (`@app.cls` with `@modal.enter`), not inside every call.
2. `tiffintally/extract/gemma.py`: remove the hard-coded `DEFAULT_MODAL_URL`; read `MODAL_EXTRACTOR_URL` and `MODAL_EXTRACTOR_TOKEN` from env only; if either is missing the Modal backend is unavailable and the sheet says so. Remove the URL from `scripts/head_to_head.py` defaults as well.
3. `docs/DEPLOY.md`: how to redeploy with the token. Do not paste the URL anywhere in docs.
4. [HUMAN] Create the secret, redeploy under a new app name or run `modal app stop tiffintally-extract`, so the old public URL stops serving.
5. Acceptance: a unit test that the Modal client sends the bearer header and refuses to run without a URL; `grep -rn "modal.run" tiffintally scripts docs README.md` returns no live URL.

## Phase 2: Make the model path correct and honest (T3-004, T3-005, T3-007, T3-008, T3-011), 5 h
Decision D1 (default): **Gemma 4 on the Gemini API is the primary extractor** (`gemma-4-26b-a4b-it`, fallback id `gemma-4-31b-it`). Confirm the id is live with a one-line `models.list` call before relying on it, and log the result. The Qwen LoRA stays as an opt-in experiment (`EXTRACTOR_BACKEND=modal`) described with its real licence.
1. **Backend choice.** Default `EXTRACTOR_BACKEND`: `gemini` when `GOOGLE_API_KEY` is set, otherwise `off` (rules). `modal` only when explicitly set. A config mistake must never silently switch to a different model.
2. **Indexed batching (T3-008).** Gemini request: number the messages (`### 0`, `### 1`, ...), ask for `{"results":[{"i":0,"events":[...]}, ...]}`, `temperature: 0`, JSON mime type. Parse by index, never by `zip`. Missing index: that message falls back to rules and is flagged `model_dropped_message`. Duplicate or out-of-range index: ignore and flag. Never extend events from one reply once per message.
3. **Guard layer after every model reply (T3-007)**, in one function `guard(model_events, rules_events, message)`:
   - model returned fewer or more rows than messages: affected messages go to review with flag `model_row_mismatch`, using the rules result;
   - model payment without an amount, and the rules find one: take the rules amount, flag `amount_from_rules`;
   - rules classify the message as feedback, complaint, refund or question, and the model says `new`: set `needs_review`, flag `model_vs_rules_disagree`;
   - quantity or action disagreement between model and rules: `needs_review`, show both ("model says 2, rules say 3");
   - roommate or "X ke liye" (secondary customer) present in the rules but missing from the model: add the rules event, flag `secondary_from_rules`;
   - unparseable model output: counts as a fallback message, not a model message.
4. **Honest labels (T3-011).** `app.py` and `prep_sheet.html`: the banner lists model name only from a successful response. Fallback says "Rules (regex) read N message(s); the model did not answer (reason)". Remove the `-fallback` suffix trick and the default-id label. The same applies to the CLI.
5. **Timeouts.** Gemini: `EXTRACT_TIMEOUT` default 30 s, at most 2 attempts, no retry on 400/401/403/404; on 429, back off once and then fall back for the rest of that paste with one clear message. A 200-message paste must finish inside 60 s or return the rules result with a visible notice.
6. **Licence hygiene (T3-004).** Fix `scripts/modal_serve.py:9` (Qwen2.5-3B is under the Qwen Research Licence, non-commercial, "Built with Qwen" required); add a `NOTICE` section in README for the adapter experiment. State in README which models are Apache-2.0 (Gemma 4, per Google; verify the licence line on the model card and quote it) and which are not.
7. **Data-use note.** In README and the post, state that on the Gemini API free tier prompts may be used by Google to improve products **(verify against Google's current terms and quote the link)**; the app sends only pseudonymised text; the demo uses only synthetic chat.
8. Acceptance tests (add them): fake Gemini-format server returns indexed results for 3 messages and exactly 3 events come back; a reply with a missing index yields a flagged fallback event for that message; a reply that duplicates events yields no duplicates; "₹500 GPay kiya" with a model amount of null ends with 500 on the ledger; "kal lunch bahut teekha tha" with model `new` ends in review; a garbage reply is counted as `fallback_messages`; the banner never contains a model id when `model_messages == 0`. A ready-made harness is in `/workspace/tt-audit3/probes/probe3_model.py` and `probe3_gemini_path.py` if you can read them; otherwise write equivalents with `http.server`.
9. Smaller option if running short: keep rules as default, ship the Gemini path behind the key, and claim nothing about a model that is not in the live demo.

## Phase 3: Correctness fixes (T3-012 to T3-017, T3-019), 5 h
Write the failing test first for each.
1. **Late-cancel total (T3-014).** `reconcile.py:418-421`: remove the `sum(1 ...)` seed. A 2-plate late cancel prints "2 plate(s)".
2. **Re-stated quantity (T3-015).** Different timestamps: latest wins, show "was 2, now 3" in the review panel. Same minute and different quantity: conflict (flag name `same_minute_conflict` is only for that case; other cases use `restated`). Suggest the cook's name automatically (a sender whose messages are mostly "ok", "done", "confirmed") and ask once; default group totals must not count the cook as a customer after she confirms.
3. **Negations and complaints (T3-016).** Add: `cancel mat karna`, `cancel nahi karna`, `nahi chahiye ... wapas` (keep the order), `aaya nahi` / `nahi aaya` / `paise wapas` (complaint, no order), `ya` between two numbers (review), Devanagari pauses (`बंद`, `छुट्टी`), a top-10 list of Gujarati/Marathi Roman forms (`jevan`, `doghanche`, `udya`, `aaje` etc.) or remove the claim from the README. Messages over 500 characters are split into sentences and processed in full, never truncated.
4. **Dates (T3-017).** Replace the free-text box with `<input type="date">` plus "Tomorrow" and "Today" buttons; server validates and returns a friendly 400, never a 500 (`2026-02-30`, `banana`, `32/13/2026`). In the parser, when every date field is 12 or below, mark the file `date_format_ambiguous` and ask the cook once (DD/MM or MM/DD).
5. **Ledger (T3-013).** Price per meal field (default ₹80, remembered in the session), `Decimal` for all money, reminders in paise-safe format (`₹99.99`), negative balances show as credit. Late cancels: one policy on both pages (the sheet says "cooked, still billed unless you accept the cancel"; the ledger matches). Add CSV export/import of balances so a cook can carry dues across days without a database.
6. **Privacy (T3-012).** Pseudonymiser: per-session, in-memory map (drop the global `data/privacy_map.db`), a token never resolves to a name from another session; keep a space around tokens (`call C020`, not `callC020`).
7. **Sessions (T3-019).** Hard cap with LRU eviction at `MAX_SESSIONS` regardless of idle time.
8. Acceptance: all probe cases in `/workspace/tt-audit3/probes/probe3_extract.out` that failed (8) now pass or are consciously documented in `docs/DECISIONS.md`; a test per item above; full suite green; `uv run pytest -q` leaves `git status` clean.

## Phase 4: Eval honesty (T3-010), 1.5 h
1. One definition of exact match everywhere: meal, qty, action, mods (date reported separately). Write it at the top of RESULTS.md. Say that run 31's 84.0% includes date and used the older test file.
2. With the key set, run **Gemma on `dev.jsonl` (60 rows) and `test.jsonl` (50 rows)** once each, plus the rules, plus the guarded hybrid. Save raw outputs under `evals/runs/<ts>/`. Report each as `model, split, n, exact match, per-field, latency p50/p95, rows where it differs`.
3. Add the per-template line: report results with and without the single template `bina mirchi ke N dabba dinner` (6 of 50 rows, label-convention driven) and say plainly which side wins. If rules beat the model, the README says so and the product positioning becomes "model proposes, rules verify".
4. Keep the one genuinely strong, honest result: base Qwen2.5-3B 66.0% to +LoRA 88.0% on the frozen synthetic test (`evals/runs/20261015_175344/head_to_head.json`), labelled as synthetic and generator-matched.
5. Dashboard: remove `C:/Users/vedan/...` paths (show repo-relative paths), one chart per (model, split), a banner "synthetic data only".
6. Move `evals/modal_run_iter_1..30.json` into `evals/retracted/` (they are void). Keep run 31.
7. Do not run the live Modal endpoint in CI.
8. Acceptance: every number in README/RESULTS/post appears in `docs/NUMBERS.md` with a file path that exists; `grep -rn "84.0\|88.0\|90.0" README.md RESULTS.md post.md` shows each only with its definition and source.

## Phase 5: Cleanup and dependencies (T3-018, T3-020, T3-021, T3-023, T3-025), 1.5 h
- Delete dead code: legacy `extract_batch`, `TinkerExtractor` (or keep, clearly marked "not used"), `forecast_*` schema fields, telemetry forecast hooks, the three redundant dashboard scripts (keep one), `data/synthetic/orders.jsonl` and `tinker_sft_train.jsonl` only if nothing reads them (grep first).
- `pyproject.toml`: remove `tabpfn-client`; move `modal` to an optional extra `experiments`; keep `numpy` only if used (one import in eval) or replace it; confirm `uv sync --no-dev` stays small and report the installed size. Do not claim a Render memory fit you did not measure.
- Voice brief: use a spoken date ("kal, 17 October"), say "Kal" for tomorrow, hide the "ElevenLabs" header when no key is set; the voice-note stub must not write a file named like an order.
- `/health` version matches `pyproject.toml`.
- Acceptance: `grep -rn "tabpfn\|forecast" tiffintally pyproject.toml` returns nothing outside comments that say it was removed.

## Phase 6: Deployment config (T3-002, T3-018), 1 h plus [HUMAN] deploy
1. `render.yaml`: `runtime: python`, a unique service name (not `tiffintally`, that Render subdomain is another product's), `buildCommand: uv sync --frozen --no-dev`, `startCommand: uv run --no-sync uvicorn tiffintally.app:app --host 0.0.0.0 --port $PORT`, `healthCheckPath: /health`, env vars: `PYTHON_VERSION` set to a Render-supported 3.12.x, `TIFFINTALLY_DEMO_MODE=true`, `EXTRACTOR_BACKEND=gemini`, `GEMMA_MODEL=gemma-4-26b-a4b-it`, `EXTRACT_TIMEOUT`, `GOOGLE_API_KEY` (`sync: false`). Verify the keys against the current Render blueprint docs and note the page you used.
2. `.env.example`: same names, correct model ids, no stale Gemma 2.
3. A "demo mode" banner in the UI: synthetic chats only, nothing stored, cold start up to a minute on the free tier **(verify on Render docs and quote)**.
4. [HUMAN] Deploy, give you the URL; then you set `docs/DEPLOY.md` to that real URL and record the response time of a cold and a warm `/health` and `/process` with the sample chat.
5. [HUMAN] .tech: claim at hacktoberfest.com/my/promos, auto-renew off, DNS to Render, confirm HTTPS. If any step asks for a card, stop and tell Vedant.
6. Acceptance: `curl -s https://<live>/health` returns `{"status":"ok","version":...}`; the sample chat gives the correct sheet (lunch 7, dinner 3, Sneha cancel, Amit pause needs review, Deepak late) with the model path **or** a clear rules-fallback notice with no model id.

## Phase 7: Honesty sweep of every document (T3-009), 2 h
Create `docs/CLAIMS.md`: a table of every factual sentence in README, RESULTS, post, DEPLOY, DECISIONS, demo-script, index footer, with the file or command that proves it. Delete or fix any row without proof.
Specific edits:
- README first screen: what it is, who it is for, the live URL (when it exists), a 3-line status ("what runs, what does not, what is synthetic"), the model used and its licence, the demo video link, AI-assistance disclosure ("built with AI coding agents, reviewed and tested by the author"), a line "Commits after the deadline: none" (update if false).
- README quickstart: only commands that exist (`serve`, `parse`, `eval`, `export-sft`); delete `forecast`.
- RESULTS.md: replace the "does not load this adapter" lines; table per Phase 4.
- Index page footer: describe the real default (which backend, what leaves the machine, pseudonymised, free-tier terms).
- `docs/demo-script.md`: rewrite to the current UI only; no forecast, no TabPFN.
- `docs/DEPLOY.md`, `docs/DECISIONS.md` ADR 002 and 003: current model, current privacy boundary.
- `PROGRESS.md`: state what is true on the date you write it.
- GitHub About (via the README note for the human): description, topics (`hacktoberfest`, `whatsapp`, `gemma`, `fastapi`, `hinglish`), homepage URL.
- Acceptance: a grep for `gemma-2`, `TabPFN`, `forecast`, `rules fallback`, `does not serve`, `no key, no chat text` finds only text that is true today.

## Phase 8: Video kit and the DEV post (T3-003), 3 h plus [HUMAN] recording and publishing
1. `docs/VIDEO.md`: a 75-second shot list matching the current UI: (0:00 to 0:10) the 10 PM chat problem, one screenshot of a messy synthetic chat; (0:10 to 0:30) paste the sample on the live site, show the banner naming what ran; (0:30 to 0:50) the sheet, the review panel ("model says 2, rules say 3"), the late cancel with the accept button; (0:50 to 1:05) the ledger with a copied reminder (nothing sent); (1:05 to 1:15) the eval table, including the line where rules win. One sentence of voiceover per shot. No claim without a file behind it.
2. `post.md` rewritten for DEV using the official template button's structure (the author pastes into it): front matter with tags `devchallenge, hf26challenge, opensource, ai`; the line "This is a submission for the Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle"; then `## What I Built`, `## Demo` (live URL, video), `## Code` (repo), `## How I Built It` (architecture: parser, extractor, guard, reconciler, ledger), `## Why Open Matters Here` (cost, privacy, niche Hinglish fine-tune with the control result, no lock-in, with the honest caveats), `## Evals` (the real table), `## Who Would Pay` (price only if Vedant supplies one; otherwise say it has not been tested), `## My First User` (only what actually happened, or "not yet"), `## Prize Categories` (only what Phase 6 and 4 prove), `## Credits`. Keep a short "what I got wrong and fixed" box (retractions) of at most 120 words with a link to `evals/retracted/README.md`. Target 900 to 1,200 words, plain voice, no marketing adjectives, no claims about numbers not in `docs/NUMBERS.md`.
3. Acceptance: every link in the post resolves; every number in the post is in `docs/NUMBERS.md`; the categories section lists only categories with a proof link in the post itself.

## Phase 9: QA with evidence, 1 h
Create `docs/QA_EVIDENCE.md` with the actual output of each, from a **fresh clone** in a temp directory:
`git clone <repo> /tmp/qa && cd /tmp/qa && uv sync --no-dev && uv run tiffintally serve &` then the sample chat through `/process`; `uv sync --all-extras --dev && uv run ruff check . && uv run ruff format --check . && uv run pytest -q`; `uv run tiffintally eval` with and without a key; `gitleaks detect`; `git status` after tests; `curl` of the live URL (cold and warm, with timings); GitHub Actions page shows green; the video plays; the post (draft preview) renders. Anything that fails is fixed or written up honestly as a known limit in the README.

## [HUMAN] gates (ask Vedant, keep working meanwhile)
1. Modal: secret, redeploy or stop the old endpoint (Phase 1).
2. Google AI Studio key (Phase 2, Phase 4).
3. Render deploy, `.tech` claim and DNS (Phase 6).
4. A real cook or food seller: consented messages or a 20-minute session (Phase 8), never committed.
5. Record the video, upload it, give you the link (Phase 8).
6. Use the official DEV template, paste, set tags, publish before Sun 18 Oct 9 PM IST (Phase 8).
7. GitHub About text, topics, homepage.

## Explicit do-not list
- Do not make any claim that a Gemma, Tinker, TabPFN, ElevenLabs, Sentry or Render result exists unless a saved run or a live URL proves it.
- Do not call Qwen2.5-3B Apache-2.0 or commercially usable.
- Do not leave the Modal URL, a key, a token or a local path (`C:/Users/...`) anywhere in the repo.
- Do not edit the frozen test or dev files, or re-record their hashes.
- Do not add heavy dependencies (torch, transformers) to the app.
- Do not hit the live Modal endpoint from tests or CI.
- Do not rewrite git history or force-push.
- Do not publish, send, or post anything for Vedant.
- Do not add features. Fix, prove, document, ship.

## Definition of Done (tick every box)
- [ ] CI green on GitHub (jobs running, not zero jobs).
- [ ] Modal endpoint requires a token or is stopped; no URL or token in the repo.
- [ ] Gemma 4 path: indexed batching, guard layer, honest labels, tests above.
- [ ] A saved run of Gemma (or `NOT RUN` with the reason) on dev and test, in `docs/NUMBERS.md`.
- [ ] Every number in README, RESULTS, post and dashboard traceable to a saved run; one definition of exact match.
- [ ] Late-cancel total, re-stated quantities, negations, date box, price field, paise-safe money all tested.
- [ ] Demo sample on the live site gives lunch 7 (or an explicit review flag for the one it cannot resolve), with the banner naming only what ran.
- [ ] Live URL on a unique Render name (and `.tech` if claimed); cold and warm timings recorded.
- [ ] Video recorded and linked.
- [ ] DEV post on the official template with tags `devchallenge`, `hf26challenge`, only provable categories, published before Sun 18 Oct 9 PM IST.
- [ ] README first screen is accurate; AI disclosure present; licence notes for every model.
- [ ] `docs/CLAIMS.md`, `docs/NUMBERS.md`, `docs/QA_EVIDENCE.md` exist and agree with each other.
- [ ] `gitleaks` clean; `git status` clean after tests.
