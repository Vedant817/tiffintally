# HF26 Week 2 · Side Hustle — Build Pack (Vedant Mahajan)

**Challenge:** https://dev.to/challenges/hacktoberfest-week2-2026-10-12
**Recommended project:** **TiffinTally**. It turns a home tiffin cook's WhatsApp order chaos into tomorrow's prep sheet, a dues ledger and a "cook for N" forecast, using open models.
**Deadline:** **Oct 18, 2026, 11:59 PM PDT = Mon Oct 19, 2026, 12:29 PM IST** (internal lock 9:00 AM IST)

## Files
| File | Purpose |
|---|---|
| 00-challenge-brief.md | Rules, dates, prizes, judging, partner matrix, ambiguities, checklist |
| 01-idea-board.md | 10 scored ideas, recommendation, runners-up |
| 02-IDEA.md | Full TiffinTally spec |
| 03-timeline.md | Day-by-day plan to the deadline |
| 04-agent-master-prompt.md | One continuous end-to-end prompt (Antigravity / OpenCode) |
| 05-day1-kickoff-prompt.md | Short day-1 prompt |
| 06-coding-agent-prompts.md | Staged prompts A–H |
| 07-evals-and-honest-benchmarks.md | Metrics, bold tests, anti-slop |
| 08-sources.md | URLs |
| 09-devto-post-template.md | Post skeleton |
| HF26_W2_SIDEHUSTLE_PACK.md | Everything concatenated |

## Human-only steps
Claim promos · create API keys and put them in `.env` / Render · create the public repo · label real messages · find and run the first-user session · point the .tech DNS · publish on DEV via the official template.

Constraints: no credit card · no local weights · never commit secrets · never fabricate results · fresh project (no reuse of earlier projects).
# 00 — Challenge Brief (Week 2: Side Hustle)

**Challenge page:** https://dev.to/challenges/hacktoberfest-week2-2026-10-12
**Launch post:** https://dev.to/devteam/join-the-hacktoberfest-open-source-ai-challenge-side-hustle-2550-in-prizes-across-18-winners-55ba
**HF26 hub:** https://dev.to/challenges/hf26 · **Credits:** https://hacktoberfest.com/my/promos
Read on Oct 13, 2026, 1:20 PM IST.

## Theme
**Side Hustle**: build something with open-weight models or open-source AI **that someone would actually pay for**. Keep it small, specific and useful, for a real person (a freelancer, a small business owner, a niche community). The open pieces must be what makes it work.
Organizer examples: a local invoice and receipt sorter for freelancers, an Etsy/eBay listing writer from photos, a menu translator for a local restaurant.
In the post, explain **why open matters**: unit cost low enough for the business to work, customer data privacy, fine-tuning for a niche, no pricing lock-in.
**Bonus:** land a first user. Did they pay? Would they? What did they ask for next?

## Dates
| Event | PDT | IST |
|---|---|---|
| Start | Oct 12, 2026 | Oct 12, 2026 |
| **Submissions due** | **Oct 18, 2026, 11:59 PM PDT** | **Mon Oct 19, 2026, 12:29 PM IST** |
| Winners | Week of Oct 19 | Same |
Internal lock: post final by **Oct 19, 9:00 AM IST**.

## Prizes (18 winners, $2,550)
- Overall (1): $250 + DEV++ + badge
- Featured ($200 each, 6): Render · TabPFN · Tinker · Arduino (UNO Q) · DigitalOcean · Gemma
- Partner ($100 each, 11): Backboard · ElevenLabs · Entire · GitHub Copilot · Mastra · MongoDB Atlas · Sentry Agent Tracing · SerpApi · Temporal · Tiger Data · .tech Domain (new)
- Completion badge for every valid submission. **One win per submission**, but you are entered in every category you list and genuinely use.

## Judging
1. **Writing Quality** (weighted most heavily): what, who it's for, why open matters
2. Relevance: open AI at the core, and someone would pay
3. Creativity
4. Technical Execution
5. Partner tech (optional)
Tie-break: most positive reactions on the post.

## Rules that matter
- **New project only.** Repo started and finished inside Oct 12–18 PDT. Commits after the deadline must be noted in the README or you risk disqualification. No PRs to existing projects.
- Open-source AI at the core (open-weight model, open agent framework, local inference, or a mix).
- **Open-sourcing your own repo:** not stated as mandatory. The rules require a new repo and say judges check "does it work"; the template asks for code. Treat a **public repo with an OSI licence (MIT)** as required in practice.
- Teams up to 4 (list DEV handles). One post per team. 18+. English for prize eligibility. AI tools allowed.
- Credit any non-trivial prior work and open-source code.
- Tags `#devchallenge #hf26challenge` (the template adds them). List partner categories in the post's **Prize Categories** section.
- Optional: DevRelay session embed (counts toward the Entire category story if Entire is used).

## Partner matrix for Vedant (no card, low disk)
| Category | Verdict | Why |
|---|---|---|
| **Gemma** ($200) | **YES** | Google AI Studio free key, no card. The core extraction model. |
| **Tinker** ($200) | **YES** | Hosted fine-tune with promo credits. Must show baseline → FT improvement. |
| **TabPFN** ($200) | **YES** | Free non-commercial key at platform.priorlabs.ai. Demand forecast from CSV. They prefer it inside an agent. |
| **Render** ($200) | **YES if no card** | Promo credit. Stop and fall back if it asks for a card. |
| Arduino | NO | No UNO Q. |
| DigitalOcean | NO | Card. |
| **ElevenLabs** ($100) | YES | Hindi/English voice summary for the cook. Promo credits. |
| **.tech Domain** ($100) | YES | Free first year from promos. **Do not enable auto-renew** ($29.99/yr). No card should be needed; stop if asked. |
| **Sentry Agent Tracing** ($100) | MAYBE | Free Developer plan; worth it if traces go in the post. |
| **GitHub Copilot** ($100) | MAYBE | Only if Actions CI and Copilot review are really used. |
| **Entire** ($100) | MAYBE | If agent sessions are shared in the write-up. |
| Mastra | MAYBE | Only if the agent is actually built on Mastra (TS). |
| SerpApi, Temporal, Tiger Data, MongoDB, Backboard | NO by default | Not core; don't claim categories you don't really use. |

## Submission template
The official "Side Hustle Submission Template" is a button on the launch post (it pre-fills a DEV editor). I couldn't read its exact headings without logging in. Based on the "How to participate" text it asks for: **What I built and who would pay · Demo · Code · How I built it / why open matters · First user (bonus) · Prize Categories**. `09-devto-post-template.md` follows that order. **Click the official template button and paste our sections into its headings.**

## Checklist
- [ ] New public repo, first commit on or after Oct 12, MIT licence
- [ ] README: what, who pays, how to run, why open, demo GIF, eval numbers, credits
- [ ] Working demo (Render or a recorded local run)
- [ ] RESULTS.md with raw numbers only
- [ ] Real first-user session notes (consent, no personal data in the repo)
- [ ] DEV post from the official template, partner categories honestly listed
- [ ] Published before **Oct 19, 12:29 PM IST**
# 01 — Idea Board (Side Hustle)

Scoring (1–5) is weighted to the judging: Writing/story ×3, Relevance (open core + would pay) ×2, Creativity ×2, Feasibility in ~5.5 days with no card and low disk ×2, Partner fit ×1. Max 50.
Excluded on purpose: Flow Pilot, MediClarity, Nexus Forge, PayHack, Wiretight, Baahar, Aaji's Pill Clerk (and anything close to them, like handwritten-document OCR or payments/bank fraud).

| # | Idea | Who pays | Pain (real) | Open core | Partners | Story | Rel | Crea | Feas | Partner | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **TiffinTally**: turns a home tiffin cook's WhatsApp order chaos (Hinglish, voice-note transcripts, "kal 2 thali no pyaaz") into tomorrow's prep sheet, dues ledger and a cooking-quantity forecast | Home tiffin and cloud-kitchen operators, ₹199–299/mo | Orders spread across WhatsApp DMs, last-minute changes, food waste, unpaid dues ("udhaar") | Gemma extraction + Tinker-tuned small open model + TabPFN forecast | Gemma, Tinker, TabPFN, Render, ElevenLabs, .tech | 5 | 5 | 5 | 4 | 5 | **47** |
| 2 | **TuitionBook**: home tutors log attendance and fees by voice note; it drafts polite fee reminders for parents | Home tutors | Fee chasing is awkward; attendance is in notebooks | Whisper-class STT + Gemma | Gemma, ElevenLabs, Render | 4 | 4 | 4 | 4 | 3 | **39** |
| 3 | **ResellerDM**: Instagram/Meesho reseller pastes customer DMs and gets structured orders, a size/stock check and reply drafts | Small Instagram sellers | Orders lost in DMs, size mix-ups | Gemma + fine-tuned classifier | Gemma, Tinker, Render | 4 | 4 | 3 | 4 | 4 | **38** |
| 4 | **GST Shoebox**: local sorter for freelancer invoices and receipts into GST-ready CSV | Indian freelancers | Quarterly GST/ITR scramble | Local Gemma vision | Gemma, Render | 3 | 5 | 2 | 4 | 3 | **36** (too close to the organizer example) |
| 5 | **Quote Coach**: freelancers paste a client brief and get a scoped, priced quote using their own past-project CSV | Freelance devs and designers | Underpricing, scope creep | Gemma + TabPFN regression on past rates | Gemma, TabPFN | 4 | 4 | 3 | 4 | 4 | **38** |
| 6 | **LatePay Radar**: predicts which client invoices will be paid late (TabPFN) and drafts chasers | Freelancers, agencies | Cash-flow stress | TabPFN + Gemma | TabPFN, Gemma, Temporal | 3 | 4 | 3 | 4 | 4 | **35** (feels near PayHack/finance; skip) |
| 7 | **BakeCost**: home bakers enter a recipe and get a cost per unit and suggested price from live ingredient prices | Home bakers | Underpricing cakes | Gemma + SerpApi prices | Gemma, SerpApi | 4 | 4 | 3 | 3 | 3 | **35** |
| 8 | **Thali Menu Card**: a small restaurant's handwritten/regional menu becomes a bilingual menu with allergen tags | Small dhabas | Tourists can't read the menu | Gemma vision, Tinker on dish names | Gemma, Tinker, .tech | 3 | 4 | 2 | 4 | 4 | **33** (organizer example + near Pill Clerk OCR) |
| 9 | **SocietyDesk**: housing society treasurer reconciles maintenance payments from UPI SMS exports | RWA volunteers | Manual reconciliation | Local model on SMS text | Gemma, MongoDB | 3 | 4 | 3 | 3 | 2 | **32** (near Wiretight banking) |
| 10 | **ClipCutter**: a podcaster's long episodes become short-clip suggestions and captions | Indie podcasters | Hours spent editing | Open STT + Gemma | ElevenLabs, Gemma | 3 | 3 | 2 | 2 | 3 | **28** (heavy media, disk) |

## Recommendation: TiffinTally (#1)
- **Who pays and why:** India's home-tiffin economy runs on WhatsApp. One cook with 30–80 daily customers loses money in three ways: missed or changed orders, over- or under-cooking, and dues nobody tracks. ₹249/mo is less than one wasted day of dal-rice.
- **Why open matters (post angle):** (a) Customer names, addresses and dues should not sit on a closed API's servers, so the tuned small model can run on the cook's own phone or laptop later. (b) Unit cost: a few thousand short messages a month on a tuned 1–3B open model is close to free, which closed per-token pricing can't match at ₹249. (c) Hinglish order slang ("half plate", "no pyaaz", "Sunday off", "Ravi bhaiya ke liye bhi") is a niche that fine-tuning visibly improves.
- **Partner stack:** Gemma (extraction and teacher), Tinker (fine-tune a small open model with a measured gain), TabPFN (tomorrow's thali count), Render (host), ElevenLabs (morning voice summary in Hindi), .tech domain.
- **First-user path:** Bengaluru has many PG/office tiffin services. Vedant asks one cook (or a family member's cook) for an anonymised week of orders and a 20-minute trial.

## Runners-up
1. **TuitionBook** (39): warm story, but fewer partner categories.
2. **ResellerDM** (38): good, but Instagram DM scraping is legally and technically awkward; it would have to rely on pasted text.
3. **Quote Coach** (38): solid TabPFN story; less emotional pull for the write-up.
# 02 — IDEA: TiffinTally

> **Tagline:** "Your WhatsApp orders, sorted before the pressure cooker's first whistle."
> Repo name: `tiffintally` · Domain: `tiffintally.tech` (claim it in promos; check it's free first)

## Problem (one real person)
Meet a home tiffin cook in Bengaluru with about 40 customers (PG students and office workers). Every evening 60–120 WhatsApp messages come in: "kal lunch 2, dinner skip", "aaj roti nahi rice", "no onion for Priya", "paying Friday", a voice note. She tallies by hand at 10 PM, cooks too much or too little the next morning, and forgets who owes ₹1,800.

## What it does (MVP)
1. **Ingest:** paste text or upload a WhatsApp **chat export .txt** (a standard feature; no scraping, no WhatsApp API). Optional: an audio note gets transcribed through a hosted open Whisper endpoint (stretch).
2. **Extract:** each message becomes structured `OrderEvent {customer, date, meal(lunch|dinner), qty, items, mods[], action(new|change|cancel|pause), payment_note, confidence}`, with Hinglish handled.
3. **Reconcile:** apply changes and cancels in time order to get **tomorrow's prep sheet** (counts per dish, special mods list, packing labels per customer).
4. **Forecast:** TabPFN predicts tomorrow's actual thali count (orders + typical late additions) from the cook's history CSV (day of week, holidays, weather, last 7 days). Show it as "Cook for about 46 (confirmed 41)".
5. **Dues:** a running ledger per customer; it drafts polite reminder messages in Hinglish for the cook to copy. **It never sends anything automatically.**
6. **Morning voice brief (ElevenLabs):** a 30-second Hindi/English summary ("Kal 41 confirmed, 5 extra expected, 6 no-onion...").
7. **Review-first UX:** low-confidence extractions are highlighted for one-tap fix, and fixes are saved as new training rows.

## Out of scope
Payments, sending WhatsApp messages, delivery routing, multi-kitchen.

## Architecture
```
chat export / paste ─▶ parser (regex: WhatsApp line format, timestamps)
                      ─▶ extractor: Tinker-FT small open model (primary)
                                    ↳ fallback/teacher: Gemma 3 via Google AI Studio
                      ─▶ reconciler (pure Python, deterministic, unit-tested)
                      ─▶ prep sheet + dues ledger (SQLite)
history CSV ─▶ TabPFN (Prior Labs API, tabpfn-client) ─▶ "cook for N"
prep sheet ─▶ ElevenLabs TTS ─▶ morning brief mp3
FastAPI + a small HTMX/vanilla front end ─▶ Render free web service ─▶ tiffintally.tech
```
- Python 3.11 + `uv`, FastAPI, SQLite, pydantic. No local model weights (disk is limited).
- **Model choice:** Tinker fine-tunes an open-weight model from Tinker's supported list (pick the smallest Llama/Qwen it offers, e.g. ~1–8B; check the list on the day). LoRA, served through Tinker's sampling API. Gemma (`gemma-3-27b-it` or the latest Gemma on AI Studio) is the baseline and labeler.
- **Privacy mode:** names are pseudonymised before any hosted call (`C001`), and the mapping stays in local SQLite. The post states honestly that hosted inference is still a third party, and that the open model is what allows moving fully local later.

## Data (honest)
- **Synthetic set:** a generator script builds about 600 Hinglish order messages from templates plus Gemma paraphrases, with gold labels from the generator. It is clearly marked synthetic.
- **Real set:** 50–150 anonymised messages from the first user, hand-labelled by Vedant. **Held out for test only.**
- **History CSV for TabPFN:** if the user has a notebook log, digitise 4–8 weeks. Otherwise the demo uses synthetic history, the post says so, and the TabPFN claim is scoped to "works on synthetic, here's the method".

## Pricing story (for "would someone pay")
- Free: 1 kitchen, 20 customers. Pro ₹249/mo: forecast, voice brief, unlimited customers.
- Compute RESULTS.md cost per 1,000 messages: FT small model vs Gemma vs a closed API list price (cite the pricing page and date). Use real token counts from logs.

## Definition of Done
- Upload an export and get a prep sheet in under 10 s for 200 messages (measured)
- Eval: baseline Gemma vs Tinker FT on the **real held-out** set, field-level F1 and exact-match per message
- TabPFN vs naive baseline (last-same-weekday) MAE
- Hosted demo URL + .tech domain + 60–90 s demo video
- First-user notes (real quotes, with consent) or an honest "not yet"
- DEV post draft in `post.md`
# 03 — Timeline (Tue Oct 13, 1:30 PM IST → Mon Oct 19, 12:29 PM IST)

About 5.5 days. Agents run continuously; **[V]** = Vedant must act.

| When (IST) | Work | Gate |
|---|---|---|
| **Tue Oct 13, eve** | [V] Claim promos (Tinker, Render, .tech; ElevenLabs if listed), AI Studio key, Prior Labs key (accept non-commercial licence). [V] Message 2–3 tiffin cooks / PG tiffin services asking for an anonymised week of orders and a 20-minute trial. Agent: scaffold repo, licence, CI, WhatsApp export parser + tests, OrderEvent schema | Repo first commit dated Oct 13 |
| **Wed Oct 14** | Synthetic generator (600 rows), Gemma baseline extractor, reconciler + bold tests, eval harness. [V] Collect real messages, anonymise, hand-label ≥50 | Baseline numbers on synthetic in RESULTS.md |
| **Thu Oct 15** | Tinker fine-tune run 1 (train on synthetic plus *non-test* real rows); eval vs baseline; TabPFN forecast + naive baseline; SQLite dues ledger | FT beats baseline on real holdout **or** an honest write-up of why not |
| **Fri Oct 16** | Front end (upload → review → prep sheet → dues), ElevenLabs brief, pseudonymisation, deploy to Render, point the .tech domain. Sentry tracing if chosen | Public URL works from phone |
| **Sat Oct 17** | [V] **First-user session** (in person or a call): she uploads her own export; record her reactions, ask "would you pay ₹249?". Fix the top 3 asks. Demo video | User notes in `docs/first-user.md` |
| **Sun Oct 18** | Final evals rerun, README, post.md full draft, screenshots and GIF, cost table from real logs | Draft done by 10 PM IST |
| **Mon Oct 19, 6–9 AM** | [V] Edit voice, paste into the **official template**, publish. **Hard stop 12:29 PM IST** | Published by 9 AM |

Fallbacks: if Tinker credits are late, ship Gemma-only and drop the Tinker claim. If Render asks for a card, record a local demo and use only the .tech domain if a free static host (GitHub Pages) can serve the landing page. If no real user replies by Fri, use a family member who cooks for others, or say honestly "first user: not yet".
# 04 — Agent Master Prompt (paste-ready)

For Google Antigravity or OpenCode (via T3 Code). Paste everything inside the fence. It runs continuously until the Definition of Done, and pauses only for [HUMAN] steps.

````markdown
# TiffinTally — HF26 Week 2 "Side Hustle" · End-to-End Build Order

You are a tireless senior team building **TiffinTally** for Vedant Mahajan's DEV Hacktoberfest 2026 Week 2 entry. Work continuously through the phases below until every Definition of Done box is checked. Commit small and often. Do not stop at sketches.

## Personas (rotate internally)
Staff engineer · PM (scope and deadline) · Indian home-kitchen domain reviewer (Hinglish, tiffin ops, dues culture) · Eval scientist (raw numbers, failure analysis) · DEV essayist (Vedant's honest, ambitious voice; he edits).

## Challenge facts
- Theme: build with open-weight models / open-source AI something **someone would actually pay for**. Explain why open matters (cost, privacy, niche fine-tune, no lock-in). Bonus: a first real user.
- Deadline: **Oct 18, 2026, 11:59 PM PDT = Oct 19, 2026, 12:29 PM IST**. Internal lock: Oct 19, 9:00 AM IST.
- Judging: Writing Quality (heaviest), Relevance, Creativity, Technical Execution, Partner tech.
- New repo, started inside the window. Tags #devchallenge #hf26challenge.
- Target categories (claim only what's genuinely used): Gemma, Tinker, TabPFN, Render, ElevenLabs, .tech Domain; optional Sentry Agent Tracing, GitHub Copilot (Actions).

## Hard constraints (NEVER violate)
- **NO CREDIT CARD.** If any signup or deploy asks for a card, STOP that path, log it in `docs/DECISIONS.md`, use the fallback.
- **LIMITED DISK.** No local model weights, no torch/CUDA installs. Hosted APIs only: Google AI Studio (Gemma), Tinker, Prior Labs `tabpfn-client`, ElevenLabs.
- **NEVER COMMIT SECRETS.** `.env` is gitignored from commit 1. Add `.env.example`. Run `gitleaks detect` (or `git diff --cached | grep -iE 'key|token|secret'`) before every push. Keys come only from the environment.
- **NEVER FABRICATE RESULTS.** Every number in README/RESULTS/post comes from a script run saved under `evals/runs/<timestamp>/`. If something wasn't run, write `NOT RUN` and why. Never invent user quotes; the first-user section is filled by Vedant only.
- **Privacy:** no real customer names, phone numbers or addresses in the repo. Real data lives in `data/private/` (gitignored). Pseudonymise before any hosted call.
- Never auto-send WhatsApp or any message. The app only drafts.
- Fresh project: do not reuse code from Vedant's earlier projects (Baahar, Aaji's Pill Clerk, Wiretight, MediClarity, Flow Pilot, Nexus Forge, PayHack).
- Vedant is early-career: keep the code readable, with one-command setup (`uv sync && uv run tiffintally serve`).

## Spec
Implement `02-IDEA.md` (pasted below or in `docs/IDEA.md`). Stack: Python 3.11, uv, FastAPI, SQLite, pydantic, HTMX or vanilla JS, pytest. Deploy: Render free web service (from `render.yaml`).

## Phases
**P0 Setup (≤2h).** Repo `tiffintally`, MIT LICENSE, README stub, `.gitignore` (.env, data/private, *.db), `.env.example`, CI (GitHub Actions: ruff + pytest), `docs/DECISIONS.md`. [HUMAN] Vedant creates the public GitHub repo and pastes keys into `.env`.

**P1 Parser + schema.** Parse WhatsApp export formats (Android and iOS, 12h/24h, multiline messages, "<Media omitted>", system lines). Use `OrderEvent` pydantic model. Tests use fixture exports you write by hand.

**P2 Data.** `scripts/gen_synthetic.py`: ≥600 Hinglish/English order messages with gold labels (seeded, reproducible), covering cancels, changes, pauses ("next week off"), multi-person orders, payments, chit-chat (no order), typos, Devanagari. Mark the file `synthetic`. Real data: [HUMAN] Vedant labels ≥50 real anonymised messages in `data/private/real_test.jsonl` using `scripts/label_cli.py` (you build it). Real rows are TEST ONLY unless Vedant chooses a split; record the split in DECISIONS.

**P3 Baseline.** Gemma via the AI Studio API with a JSON-schema prompt. Retry and validate. Log tokens and latency.

**P4 Reconciler.** Deterministic: time-ordered apply of new/change/cancel/pause gives the prep sheet + packing labels + mods list. 100% unit-tested, including bold tests (see 07).

**P5 Tinker fine-tune.** Build a chat-format SFT set from synthetic (+ Gemma-labelled, human-spot-checked) rows. LoRA on the smallest suitable open model Tinker supports. Save config, steps, loss curve, cost. Evaluate on the SAME held-out sets as the baseline. If FT is worse, say so and analyse it. Never cherry-pick.

**P6 TabPFN forecast.** `tabpfn-client` regression on the history CSV: features dow, is_holiday (India list), confirmed_orders, lag7, rolling mean; target = actual plates cooked. Time-based split. Compare MAE against naive (same weekday last week) and against confirmed-only. Wrap it as a tool the agent calls ("how many to cook?").

**P7 App.** Upload/paste → review screen (low-confidence rows highlighted, one-tap fix, fixes saved to `data/private/corrections.jsonl`) → prep sheet (printable) → dues ledger with drafted Hinglish reminders (copy button, never send). ElevenLabs morning brief mp3 (cache it, show the character count used). Mobile-first.

**P8 Deploy.** Render via `render.yaml`. Env vars are set in the Render dashboard by [HUMAN]. Health check. Demo mode loads synthetic data only. [HUMAN] .tech domain DNS → Render custom domain. Optional: Sentry tracing on extraction calls (latency/tokens); screenshot the traces.

**P9 Evals + RESULTS.md.** Run `uv run tiffintally eval --all`. Tables come from JSON in `evals/runs/`. Include a cost per 1,000 messages from real token logs and dated list-price citations.

**P10 Write-up.** Build `post.md` from `09-devto-post-template.md`: a story-first hook (the 10 PM tally), what it does, who pays and why ₹249 works, why open matters (with numbers), how it's built, evals with failures, first user (Vedant fills it), Prize Categories (only real ones), credits. Add a 60–90 s demo script `docs/demo-script.md`. Run a final secret scan.

## [HUMAN] pause points (stop and ask, then continue other work)
Keys/promos · GitHub repo creation and push permission · real data labelling · Render dashboard and env · domain DNS · first-user session · publishing on DEV.

## Definition of Done
- [ ] CI green; ≥40 tests including all bold tests in 07
- [ ] Baseline vs FT table on real holdout (or a documented reason it's missing)
- [ ] TabPFN vs naive MAE table
- [ ] p50/p95 latency for 200 messages, measured
- [ ] Live URL + .tech domain, or a recorded local demo with the reason
- [ ] README, RESULTS.md, DECISIONS.md, post.md complete; no secret in git history
- [ ] Every claim in post.md is traceable to a file in the repo

Keep a running `PROGRESS.md` (timestamp IST, what's done, what's next, blockers). If you're blocked on a [HUMAN] step, keep working on everything else.
````
# 05 — Day 1 Kickoff Prompt (short)

````markdown
You are building TiffinTally (spec in docs/IDEA.md) for DEV HF26 Week 2 "Side Hustle"; deadline Oct 19, 12:29 PM IST. Today do only P0–P2 of docs/MASTER_PROMPT.md:
1. Scaffold: uv project, FastAPI skeleton, MIT licence, .gitignore (.env, data/private/, *.db), .env.example, GitHub Actions (ruff + pytest).
2. WhatsApp export parser + OrderEvent schema, with ≥15 tests on hand-written fixtures (Android and iOS formats, multiline, media-omitted, system lines, Devanagari).
3. scripts/gen_synthetic.py → data/synthetic/orders.jsonl (≥600 rows, seeded, gold labels, includes cancels/changes/pauses/no-order chatter).
4. scripts/label_cli.py for Vedant to label real messages into data/private/real_test.jsonl.
Rules: no credit card, no local model weights, never commit secrets, never invent numbers. End with PROGRESS.md, and ask me for the [HUMAN] items you need (keys, repo push, real data).
````
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
# 07 — Evals & Honest Benchmarks (TiffinTally)

**Rule zero:** if it didn't run, it isn't published. `NOT RUN` beats a fake number. Every table is generated from `evals/runs/*.json`.

## A. Extraction (Gemma baseline vs Tinker FT)
- Test sets: (1) synthetic test split (20%, seeded, never trained on); (2) **real held-out** (≥50 human-labelled, never trained on). Report them **separately**; real is the headline.
- Metrics: field-level P/R/F1 (customer, meal, qty, action, mods), per-message exact match, JSON-valid rate, p50/p95 latency, tokens, cost per 1k messages.
- Critical metric: **cancel/pause recall** (a missed cancel means wasted food and an angry customer). Report it on its own.
- Show 5 real failure examples (anonymised) in RESULTS.md.

## B. Bold tests (must exist and pass, or be marked xfail with an issue)
1. "kal lunch cancel" after an earlier "kal lunch 2" → tomorrow lunch for that customer = 0.
2. Order then change at 11:58 PM, then the cutoff → the change applies; a message after the cutoff is flagged "late", not silently applied.
3. "Priya ke liye bhi ek" from Ravi → a second customer is linked, not double-counted for Ravi.
4. "Sunday off" → no Sunday order for that customer, even with a standing daily order.
5. Pure chit-chat ("thank you aunty, khana mast tha") → zero orders.
6. Devanagari message "कल दो थाली" → qty 2.
7. Payment note "₹1500 GPay kiya" → ledger credit, never an order.
8. Duplicate forwarded message → counted once.
9. Malformed model JSON → retry, then route to review; never drop silently.
10. Missing API key → clear error in the UI; the demo still works on cached synthetic results.
11. Secret scan: CI fails if a key-like string is in the repo.
12. Nothing in the codebase can send a WhatsApp message or SMS (grep test).

## C. Forecast (TabPFN)
- Time-based split, no shuffling. Baselines: naive lag-7, confirmed-only. Metrics: MAE, RMSE, % days within ±3 plates.
- State n_train/n_test and whether the history is **real or synthetic** in every table.
- If TabPFN doesn't beat naive, publish that. It's still an honest story.

## D. System
- End-to-end time for a 200-message export (p50/p95 over 5 runs).
- Cost per kitchen per month = measured tokens × dated list price. Show the formula.

## E. First user (Vedant only)
- Consent recorded. Quote them only with permission; no personal data.
- Record: time-to-prep-sheet vs her usual tally time (stopwatch, n=1, say so), the corrections she made, "would you pay ₹249?" (verbatim answer), and her top asks.
- If no user: write "Not yet. Here's who I've asked." Never invent one.

## Anti-slop
No tuning on test sets. No "~95% accurate" without a run file. No claiming partner categories that are only bolted on.
# 08 — Sources (read Oct 13, 2026 IST; re-verify API shapes before building)
- https://dev.to/devteam/join-the-hacktoberfest-open-source-ai-challenge-side-hustle-2550-in-prizes-across-18-winners-55ba
- https://dev.to/challenges/hacktoberfest-week2-2026-10-12 (rules, FAQ, partner descriptions)
- https://dev.to/challenges/hf26 · https://hacktoberfest.com/my/promos
- Gemma via Google AI Studio: https://ai.google.dev/gemma · https://aistudio.google.com
- Tinker: https://thinkingmachines.ai/tinker/ (check supported models and docs on the day)
- TabPFN: https://platform.priorlabs.ai · https://github.com/PriorLabs/tabpfn-client
- Render free tier: https://render.com/docs/free
- ElevenLabs: https://elevenlabs.io/docs
- WhatsApp chat export: https://faq.whatsapp.com/1180414079177245
- Domain context: India's home/tiffin food economy runs on WhatsApp ordering (general knowledge; get the real numbers from the first user rather than citing unverified market stats).
# 09 — DEV Post Template (fill into the official "Side Hustle Submission Template")

```markdown
---
title: "TiffinTally: I taught an open model to read my tiffin aunty's WhatsApp so she stops cooking for ghosts"
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).*

## What I Built
<!-- Hook: 10 PM, 97 unread WhatsApp messages, a notebook, a pressure cooker. -->
<!-- One paragraph: what TiffinTally does, in her words. Screenshot of the prep sheet. -->

## Who Would Pay (and Why ₹249/month Works)
<!-- Her economics: N customers × ₹X/thali; waste per over-cooked day; unpaid dues. -->
<!-- Measured cost per kitchen per month (link run file). -->

## Demo
<!-- Live: https://tiffintally.tech · 60–90 s video · demo mode uses synthetic data -->

## Code
<!-- GitHub repo link (MIT). {% github vedant/tiffintally %} -->

## How I Built It
<!-- Architecture diagram. Gemma as teacher/baseline → Tinker LoRA on a small open model → deterministic reconciler → TabPFN forecast → ElevenLabs brief. -->
<!-- Agent session: DevRelay embed/link (optional). -->

## Why Open Matters Here
<!-- 1. Unit cost: table FT-small vs Gemma vs closed list price (dated). -->
<!-- 2. Privacy: pseudonymisation + path to fully local. Be honest that hosted inference is still a third party today. -->
<!-- 3. Niche: Hinglish order slang. Baseline vs FT on REAL held-out (numbers + 2 failure examples). -->
<!-- 4. No lock-in: weights and adapter are portable. -->

## Evals (the honest bit)
<!-- Tables from RESULTS.md, cancel recall, what's still broken. -->

## My First User
<!-- <<VEDANT FILLS>>: who (anonymised), what she did, verbatim "would you pay?", what she asked for next. Or "not yet" honestly. -->

## Prize Categories
<!-- Only those genuinely used: Best Use of Gemma, Best Use of Tinker, Best Use of TabPFN, Best Use of Render, Best Use of ElevenLabs, Best Use of a .tech Domain [, Sentry Agent Tracing] -->

## Credits
<!-- Open-source libs, docs, anyone who helped. Note any post-deadline commits here and in README. -->
```
