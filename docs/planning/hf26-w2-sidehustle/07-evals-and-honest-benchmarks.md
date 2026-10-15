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
