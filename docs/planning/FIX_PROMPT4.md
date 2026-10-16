# FIX_PROMPT4: make TiffinTally's engineering and evaluation real

Paste everything below this line into the coding agent (Antigravity or OpenCode via T3 Code). It is self-contained. Work in the repo `Vedant817/tiffintally` on a new branch `fix/round4-honest-eval`. Do not push to `main`; open a PR or leave the branch for Vedant to review.

---

## 0. Who you are and what this round is for

You are the **Builder** on TiffinTally, a tool that reads a home cook's WhatsApp order chat and produces a prep sheet and a dues ledger. An independent audit (docs/review/AUDIT4.md; copy it in as the first commit) found that the **engineering and the evaluation are not yet trustworthy**. This round is **technical only**. Do not touch the DEV post, video, deploy, domain or rules work.

The goal of this round: after it, every number the project publishes comes from a script that anyone can rerun on saved per-row outputs, the pipeline stops losing data, the ledger is correct, and nothing is tuned on the test set.

Read first, in this order: `docs/review/AUDIT4.md` (the 26 findings, IDs T4-001..T4-026), `probes/` (copy `probes/test_core.py`, `helpers.py` and the other probe scripts into `tests/probes/`; they are regression tests that currently fail), `RESULTS.md`, `docs/QUESTIONS.md`, `data/synthetic/split_report.json`, `scripts/head_to_head.py`, `scripts/modal_serve.py`, `tiffintally/reconcile.py`, `tiffintally/extract/gemma.py`, `tiffintally/extract/base.py`, `tiffintally/eval.py`.

## 1. Roles (play all three, in this order, and keep them separate)

1. **Builder.** Implements one phase at a time, test first.
2. **QA persona ("Skeptic").** After each phase, switch role. The Skeptic did not write the code. Its job is to *try to break the phase*: rerun the acceptance tests from a clean checkout, run the probes, try three inputs the Builder did not think of, and write `evidence/phaseN-qa.md` with: commands run, raw output pasted, PASS or FAIL per acceptance item, and anything surprising. A phase is not done until the Skeptic writes PASS with evidence. The Builder may not edit `evidence/*.md`.
3. **Consultants (consult protocol).** When in doubt, do not guess and do not ask the human. Write a one-page memo in `consult/NNN-topic.md` addressed to the right consultant, answer it yourself in that voice with sources, and act on it. Use:
   - **Researcher**: facts about WhatsApp export formats, Hindi/Hinglish/Marathi/Gujarati usage, Indian tiffin pricing, library behaviour. Cite URLs you actually fetched.
   - **Architect**: where state lives, purity, module boundaries, failure modes.
   - **Statistician**: metric definitions, confidence intervals, tests, sample size. The Statistician must refuse to sign off on any claim whose interval includes zero or which lacks n.
   If a consultant memo says "needs a human decision", add it to `HUMAN_TODO.md` and keep working on something else.

## 2. Anti-fabrication rules (non-negotiable)

- **Every number** in README, RESULTS.md, post.md, the dashboard, or a commit message must come from a file under `evals/final/` produced by a script in `scripts/`. Add a table `docs/NUMBERS.md` listing: number, file:key, script, git SHA, date. No hand-typed metrics anywhere.
- **Never invent a result.** If a run did not happen, write `NOT RUN` and the reason. If a script fails, report the failure; do not substitute an estimate.
- **Never describe a regex result as a model result,** or the reverse. Every result row carries `system` (regex, base, adapter, gemini, hybrid), `prompt_sha256`, `code_sha`, and `n`.
- **Never edit `data/synthetic/test.jsonl`, any gold label in it, or `split_report.json` hashes after you have scored it.** If a test row is wrong, add it to `data/synthetic/test_errata.json` with a reason and report scores both with and without it; do not edit the row.
- **Never change a label after seeing a result that depends on it.** Label changes require a dated errata entry written *before* rerunning.
- **No tuning on test.** Rules and prompts may be fitted to `train` and a **new** `dev2.jsonl` only (Phase 4 creates it). A CI test must assert that every literal pattern in `_canonical_mods` and similar vocabularies occurs in train or dev2.
- No secrets in git. Run gitleaks before every push-ready commit. Do not print tokens.

## 3. Do-not list

- **No retraining** and **no call to the paid Modal endpoint** without the exact words "approved: train" or "approved: gpu calls <N>" from Vedant in `HUMAN_TODO.md` answered. Default GPU budget this round: **0 calls**. If approved, the cap is the number written by Vedant; stop at the cap and report.
- Do not stop, redeploy or modify the Modal app. That is Vedant's account.
- No new dependency larger than 5 MB; no torch, no model weights, no `.venv` in git. Vedant has limited disk. Vedant has **no credit card**: use only free tiers that need none (the Gemini API free tier through Google AI Studio is allowed for the comparison baselines, key supplied by Vedant via env var, never committed).
- Do not weaken a test to make it pass. Do not delete a probe because it fails.
- Do not rename or remove `evals/retracted/`.
- Do not add canned outputs, cached predictions presented as live, or special cases keyed on customer names or sample texts.

## 4. Ordered phases

Each phase ends with: green `ruff check`, `ruff format --check`, full `pytest`, QA evidence file, and one commit with a message that names the finding IDs. Do the phases in order; do not start N+1 until the Skeptic passes N.

### Phase 0: baseline and guardrails (about 1 h)

1. Create the branch. Commit `docs/review/AUDIT4.md` and `tests/probes/` (probe tests marked `@pytest.mark.xfail(strict=True, reason="T4-0xx")` for each known failure, so the suite stays green but any fix flips them to XPASS and forces you to remove the marker).
2. Add `scripts/check_claims.py` that lists every percentage and n in `README.md`, `RESULTS.md`, `post.md`, `evals/dashboard.html`, `docs/*.md`, and fails if it is not listed in `docs/NUMBERS.md`. Wire into CI.
3. Add `EXTRACTOR_BACKEND=off` as the only CI mode (already so); add a CI job that runs `tests/probes`.
- Acceptance: `pytest` green on a clean clone with `EXTRACTOR_BACKEND=off`; `check_claims.py` fails on current README (it quotes 84.0%) and passes after you add that number to NUMBERS.md with its source `evals/modal_run_iter_31.json` and the definition that includes `date`.

### Phase 1: stop losing and inventing data in the model path (T4-004, T4-005, T4-009, about 3 h, no GPU)

1. `scripts/modal_serve.py:_clean_event` must pass through **all** schema fields (`customer, secondary_customer, date, meal, qty, items, mods, action, payment_amount, payment_note, confidence`) with type validation. **No silent defaults**: a missing or invalid `meal`, `action` or `qty` makes the event `invalid` with a reason; the client turns it into a `needs_review` event, never into `lunch/new/1`. Same in `tiffintally/extract/base.py:parse_and_validate_llm_json`.
2. **Customer comes from the parsed sender, always.** Ignore the model's `customer`. Keep `secondary_customer` only if it appears in the message text (after de-pseudonymisation).
3. Payments: an event with `needs_review`, any `prompt_injection*` flag, or `audit_flags` must **never** credit the ledger. Self-reported payments are stored as `claimed` and appear in the ledger as "claimed, not confirmed" until the cook taps confirm (add `confirmed_payments` set in the session; default unconfirmed). A message containing an order and a payment yields **both** events. Future-tense promises ("kar dunga", "kal bhejunga", "will pay") are never payments.
4. Add `tests/test_modal_integration.py`: a fake endpoint that runs the **real** `modal_serve._parse` and replies with gold JSON (see `tests/probes/modal_path_mock.py`) and drives the **real** `GemmaExtractor` modal branch. Assertions: perfect-model reply for the demo sample gives lunch 7, Tanvi has a plate, Vikram's ₹1,500 appears as a claimed payment; omitted `customer` does not create `Customer`; a reply naming another customer is ignored.
- Acceptance: probes `test_secondary_customer_*`, `test_injection_in_message_does_not_change_dues` pass; `tests/test_modal_parser.py:74` rewritten to assert the *new* behaviour (unknown action becomes `invalid`, not `new`); the mock test shows 0 lost fields on a 20-row gold sample.

### Phase 2: reconcile and ledger correctness (T4-006, T4-007, T4-015, T4-016, T4-018, about 4 h)

1. Make `reconcile_orders` and `reconcile_ledger` **pure**: no mutation of input events (deep-copy at the boundary or return annotations separately). Calling them in either order must give identical results (probe `test_ledger_independent_of_whether_sheet_ran_first`).
2. Replace the `day = label` key with a **calendar date** resolved from each event's own message timestamp (reuse `event_matches_target` logic). One function `plates_by_day(events) -> {(customer, date, meal): qty}` feeds both the sheet and the ledger. Ten evenings of "kal lunch 2" must bill 20 plates.
3. One documented policy (put it in `docs/POLICY.md`) for: late orders, late cancels, restated orders, `after_midnight`. The sheet and the ledger apply the **same** policy. Add the Hypothesis property `sheet total == ledger plates for the target day` and keep it green over 500 examples.
4. Money: integer paise or `Decimal`; reminder prints exact rupees and paise; price per meal configurable (form field with default ₹80, stored in session); CSV export and import of previous balances so a month works without a database.
5. Secondary customer: one meaning. Schema: `qty` is the **total plates this message orders**; `secondary_customer` receives `secondary_qty` (default 1) of them. Update reconcile, extractor, prompt wording, and **relabel in a new file** `data/synthetic/relabel_v2.jsonl` (do not edit the frozen files). Fix the five train rows "roommate X ka lunch cancel, mera regular bhejna" in the same errata.
6. Alias suggestions: `Ravi Kumar` vs `Ravi` appear as a "merge?" review item, applied only when the cook confirms.
- Acceptance: all `tests/probes/` sheet/ledger probes pass (no xfail left for T4-006/007/015/016/018); property tests pass with `--hypothesis-seed=0` and 3 other seeds.

### Phase 3: extractor correctness (T4-013, T4-014, about 3 h)

Fit rules to **train and the new dev2 only** (created in Phase 4 step 1; do Phase 4 step 1 now if needed).
1. Negation: "cancel mat karna", "cancel nahi karna, 2 hi chahiye", "don't cancel" are not cancels.
2. Uncertainty: "2 ya 3", fractions, "pata nahi" go to review with a reason, never a silent pick.
3. Any message with a digit or a meal word whose result is `none` and has no review flag goes to review (**silent-drop rate must be 0** on train, dev2).
4. Dates: per-clause resolution so "kal lunch 1, aaj roti nahi extra rice" is tomorrow's lunch (the `aaj` belongs to the rice request); weekday names and "parso" resolve against the message timestamp.
5. Multi-intent: order plus payment in one message gives both events; "Sunday off" alone gives a pause.
6. Replace the demo sample in `index.html` and `docs/demo-script.md` with **held-out phrasing** (not in train, dev or the prompt examples), and add `tests/test_demo_sample.py`: lunch = 7 and Vikram's claimed payment = ₹1,500 on the regex path and on the mock model path.
- Acceptance: probe extraction tests pass; a new `scripts/regex_report.py` prints regex exact match on train, dev2, test with the cleaned rules (record in `evals/final/regex.json`); report the regex-on-test number **once**, after freezing rules.

### Phase 4: an honest evaluation (T4-001, T4-002, T4-003, T4-008, T4-010, about 6 h plus human labelling)

1. **New splits.** Do not edit the frozen files. Create `data/synthetic/dev2.jsonl` (60 rows) from **train-disjoint templates** written in a *different style* (see step 5) so it is held out from the adapter too. Record hashes in `split_report.json` under `frozen_v2`. `dev.jsonl` is a train subset; mark it `dev_in_train` in the report and stop using it as a tuning set.
2. **Remove test tuning** (T4-002). Delete the five literals (`no spic`, `replace curd`, `extra sabzi`, `kadak roti`, `vadhare`) and any other rule you cannot justify from train or dev2. CI test: every literal in the vocabulary functions must occur in train or dev2. Record the cleaned-regex score on test.
3. **One scorer module** `tiffintally/scoring.py`, used by *every* script (eval, head_to_head, modal_finetune, dashboard). Define two metrics and name them everywhere:
   - `strict`: meal, qty, action, canonicalised mods (a fixed vocabulary map in `data/vocab/mods.json`; unknown mods score wrong), `payment_amount`, `secondary_customer`.
   - `lenient`: meal, qty, action only.
   Multi-event messages compare as sets of events. An unparseable or empty reply is `wrong` unless gold is `none`; chit-chat rows must be reported separately from order rows. mods compared as sets. No metric is called F1 unless it is F1.
4. **Per-row artifacts.** Every eval writes `evals/final/<system>/<split>.jsonl` with `id, text, raw_output, parsed, gold, per_field_ok, strict_ok, lenient_ok, latency_ms` and `evals/final/<system>/<split>.meta.json` with `code_sha, prompt_sha256, adapter_id, adapter_sha, max_new_tokens, batch_size, dtype, decoding, n, date`. Nothing is summarised from memory.
5. **Leakage check script** `scripts/leakage_report.py`: for every test and dev2 row print nearest train neighbour by masked-signature and character 4-gram Jaccard and edit ratio; list sibling-template pairs; **fail** if any test row has Jaccard at or above 0.6 to a train row with the same label, or if any literal in the prompt examples equals a test row. Include the probe's numbers as the baseline (`probes/leakage.out`: 3 test rows at or above 0.5).
6. **Statistics script** `scripts/compare.py`: paired comparison from two per-row files: n, templates, discordant counts, exact McNemar, **template-clustered bootstrap** CI (20,000 draws, seed fixed), Wilson CIs per system, leave-one-template-out table, per-template breakdown. The Statistician memo must state in one sentence what the data does and does not support, and the README repeats **only** that sentence.
7. **Run-to-run variance.** Add `scripts/variance.py`: for the mock or offline systems, run 5 times varying batch size and order; for GPU systems record batch size 1 vs 20 and report the row-level flips (needs GPU approval, see Section 3). The finding "88 vs 90 is one row" must be reproduced or retracted with data.
8. **Real held-out set (human, see Section 6).** Wire it in as `data/private/real_test.jsonl` with a required `provenance` block (collector, date, consent, source=`collected_from_cook` or `written_by_vedant_blind`, labeller, label_date, second_labeller). The loader refuses a file without it. Report real-set results separately from synthetic, with n; **if n < 100, say so in the same sentence as the number.**
9. **Retire the three-number problem.** README, RESULTS.md, dashboard show one table: system, split, metric (strict and lenient), n, Wilson CI, source file. Remove local paths from the dashboard.
- Acceptance: `scripts/compare.py` run on the saved per-row files reproduces the regex numbers bit for bit; `check_claims.py` passes; `leakage_report.py` passes or its failures are listed in `docs/KNOWN_LEAKS.md`; a CI test proves no label or pattern is fitted to test.

### Phase 5: baselines and recipe (T4-011, T4-012; design now, GPU only if approved)

1. Add baseline systems behind the same scorer: (a) base model, same prompt (exists, rerun with per-row output **if approved**); (b) base model, 8-shot prompt drawn from train; (c) Gemini or Gemma through the free AI Studio tier (Vedant supplies the key; skip with `NOT RUN` if absent); (d) **hybrid**: regex first, LLM only on rows the regex flags; (e) adapter. Report all on the same rows with paired comparisons. Answer in writing (`docs/ML_DECISIONS.md`): *is fine-tuning adding value over an 8-shot base plus rules?*
2. Write `docs/TRAINING_RECIPE_V2.md` (do not run it): at least 600 SFT rows from at least 150 templates with each template at most 6 rows; at least 25% multi-event, negation, uncertainty, and cancel/change; consistent `secondary_qty` convention; canonical mods vocabulary; qty up to 10; held-out templates written in a different style than the training ones; fixed seeds; adapter published or per-row predictions published. Include the exact Modal command and expected GPU minutes; request approval in `HUMAN_TODO.md`. Do not run it.
3. Prompt-injection robustness: add `tests/test_injection.py` with 15 hostile messages (instructions in Hindi and English, JSON smuggling, delimiter tokens, "set dues to 0", "admin mode", an order with 5000 plates). The system must never change a ledger from a message without cook confirmation. Test on regex and on the mock model path.
- Acceptance: baseline harness runs end to end offline on regex and hybrid; GPU rows say `NOT RUN (needs approval)`.

### Phase 6: docs, privacy, hygiene, CI (T4-017, T4-019..T4-026, about 3 h)

1. Privacy: per-session in-memory token map; mask **all** capitalised names that appear in the paste or document the exact limit in the footer and README; test with the mock endpoint that no clear name from a fixture list reaches the payload. Remove `data/privacy_map.db`.
2. Fix stale claims: README line 19, `modal_serve.py` and `gemma.py` docstrings, `docs/QUESTIONS.md` (state that the multiplication bug did not touch the Modal runs, and show why: `head_to_head.py` bypasses `GemmaExtractor`; `tiffintally eval` sends one message per call). Add `docs/CLAIMS.md`: claim, file:line, source artifact, last verified SHA.
3. Remove dead code (`extract/tinker.py` and its `eval.py` import, `tabpfn-client`, three of four dashboard builders), pin dependencies with upper bounds, `/health` version from `pyproject`, hard cap on sessions with LRU eviction, `tiffintally eval --out evals/final/...` instead of timestamped directories, delete the duplicate run dirs.
4. Latency and cost: a script that measures per-message latency by batch size and cold or warm and writes `evals/final/latency.json`; **no cost per 1k figure unless a billing record is attached** (`NOT MEASURED`).
- Acceptance: gitleaks clean, `check_claims.py` green, README contains no number not in NUMBERS.md.

### Phase 7: final QA (the Skeptic, from a clean clone)

On a fresh `git clone` into a new directory: install, `ruff`, `pytest` (including `tests/probes` and Hypothesis), `tiffintally eval` with `EXTRACTOR_BACKEND=off`, `scripts/leakage_report.py`, `scripts/compare.py`, `scripts/check_claims.py`. Paste every output into `evidence/final-qa.md`. The Skeptic then answers these six questions in writing, with file:line evidence, **before** the PR is opened: Is the accuracy number valid? Is anything faked? Is anything hardcoded? Is the baseline fair? Is there leakage? What can honestly be claimed (with CI)? If any answer is "unknown", say so.

## 5. Final report format (what you send back)

1. One paragraph: what changed, what is still not done.
2. A table: finding ID, status (fixed / partly / not done), commit SHA, test name.
3. The honest-numbers table from `docs/NUMBERS.md`.
4. Anything you could not do and why (GPU approval, missing real data).
5. The `HUMAN_TODO.md` list.

## 6. Human-only list (put this file in the repo as `HUMAN_TODO.md` and keep it current; the agent cannot do these)

1. **Real held-out set, labelled by hand. This is the single most valuable thing for the project.**
   - Collect **100 to 150 real messages** from a real tiffin or mess group, a family or roommate order chat, or from people you ask directly (a free Google Form is fine, no card). Get consent, remove phone numbers, and replace names with first names or initials. Use the WhatsApp export, not retyped text. Save as `data/private/raw_real.txt` (this path is gitignored; do not commit raw chats).
   - If you truly cannot get real chats, **write 100 messages yourself, blind**: do not look at `gen_synthetic.py`, `train.jsonl` or the system prompt; write the way you or your family actually message. Ask 3 to 5 friends for 20 each, unprompted. Mark the file `source = written_by_vedant_blind`. Call it "human-written", never "real".
   - Label it by hand with `scripts/label_cli.py`: for every message, record every event (meal, qty, action, mods using the canonical vocabulary in `data/vocab/mods.json`, payment amount, secondary customer). **Do not run any model first and do not look at model output while labelling.**
   - Protocol: label all rows; wait at least 24 hours; relabel a random 30 without looking at the first pass; report agreement (Cohen's kappa on action and exact-match agreement on the full label). If agreement is below 90%, write the disagreements down and fix the *protocol*, not the labels after scoring.
   - Split it **before anything is scored**: 40 rows to `real_dev.jsonl` (the agent may tune on these) and the rest to `real_test.jsonl` (frozen with SHA-256 the moment it is saved; the agent may run it **once per system** and never inspect individual failures to tune).
   - Add the `provenance` block described in Phase 4 step 8. Never commit raw chat text to a public repo; commit the pseudonymised labelled rows only if the people consent, otherwise keep `real_test.jsonl` private and publish only per-row correctness booleans plus aggregate numbers.
2. Decide GPU approvals in `HUMAN_TODO.md`: (a) rerun the adapter and the no-adapter control **with per-row output saved** (about 120 calls, same as the original run); (b) retrain on `TRAINING_RECIPE_V2` (only after Phase 5 is reviewed). Answer with the exact words `approved: gpu calls 120` or `approved: train`, or `declined`.
3. Provide a Google AI Studio key as the environment variable `GOOGLE_API_KEY` if you want the Gemini or Gemma baseline (free tier, no card). Never paste it into chat or git.
4. Redeploy or stop the Modal app with the bearer token (your account; the agent must not touch it) and confirm a call without the token returns 401.
5. Decide the licence story: the adapter is on `Qwen2.5-3B` (Qwen research licence, non-commercial). Choose whether to (a) keep it as a research artefact and present the rules plus hosted Gemma as the product path, or (b) retrain on a permissively licensed base. The agent will document either choice; it will not choose.
6. Review the PR, especially `docs/NUMBERS.md`, `docs/POLICY.md` (late-order and restatement policy) and the relabelled secondary-customer convention, and approve in writing.

## 6b. If you are unsure

Write the consult memo, answer it in the consultant's voice, and keep going. Stop and report only for: GPU spend, anything touching Modal or secrets, changing a frozen file, or deleting data you did not create.
