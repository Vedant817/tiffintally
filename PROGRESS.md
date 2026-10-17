# TiffinTally Build Progress

**Start Date:** 2026-10-13 13:30 IST
**Target Deadline:** 2026-10-18 11:59 PM PDT (2026-10-19 12:29 PM IST)
**Internal Feature Freeze:** 2026-10-19 09:00 AM IST

`RESULTS.md` is the status that counts. The 100% real-message score, the Tinker
3B claim, the TabPFN rupee saving, the edge latency and the first-user story were
all retracted on 14 Oct 2026 after a self-review found they were not measurements.

> The 13 Oct entries below claimed "Verified complete traceability of all metrics
> in post.md". That was false at the time it was written. They are kept as a log
> of what was believed then, not as a claim about what is true now.

---

## Open items

Ordered by the 15 Oct self-review (`docs/review/REDTEAM2.md`).

| # | Finding | State |
| :--- | :--- | :--- |
| F1 | No open model actually runs; default id no longer served | **done** — Modal-hosted extractor |
| F2 | No demo link or video | **demo link done** — live on Render; video still needed |
| F3 | Post off-template, missing tags and Prize Categories | **done** |
| F4 | `eval` rewrites the honest RESULTS.md | **done** |
| F5 | Extractor turns complaints and pauses into orders | **done** |
| F6 | Ledger double-bills changes and charges cancelled meals | **done** |
| M1 | Model failure silent and mislabelled | **done** |
| M2–M6 | Late cancels, post-midnight, order dependence, "ek aur", date format | **done** |
| M7–M11 | Path traversal, shared state, weak masking, no upload caps | **done** |
| M12 | Test set used for tuning | **done** — frozen, hashed |
| M13 | Forecast worse than doing nothing | **done** — deleted |
| M14 | Post reads as an apology | **done** |
| M15 | No first user | **open — needs a real cook session** |

## Blocked on a human

- [ ] Push to `origin/main`
- [x] Render deploy (free, no card) → live URL for the post — **done**:
  <https://tiffintally-lbn2.onrender.com>, `/health` returns `200 {"status":"ok","version":"0.1.0"}`.
  No model key is set on that service, so it answers with the rules path and says so.
  See `docs/DEPLOY.md`.
- [ ] `.tech` DNS → Render custom domain (the app is live on the `onrender.com` host;
      no domain is attached yet)
- [ ] 60–90s screen recording
- [ ] First-user session with a real cook (consent, no PII in repo)

## Log

### 2026-10-13 — v0.1 built
Repo, parser, schema, synthetic generator, labeling CLI, pseudonymizer, heuristic
extractor, Gemma 2 extractor, reconciler, ledger, Tinker SFT path, TabPFN
forecaster, FastAPI app, ElevenLabs brief, eval harness, `post.md`.
All checked off at the time, including items later retracted.

### 2026-10-14 — v0.2 honest
Round-1 self-review found the fake first user, fake edge benchmark, leaked 100%
scores and phantom customers. All removed or retracted. 84 commits, gitleaks
clean, 104 tests green.

### 2026-10-15 04:40 IST — round-2 fixes, Phase 0 (hygiene)
- [x] Planning pack and self-reviews moved to `docs/planning/`, `docs/review/`
- [x] `docs/README.md` states these are planning notes, not evidence
- [x] `evals/telemetry.jsonl` untracked; tests write telemetry to a tmp path
- [x] Sentry never initialises under pytest (`TIFFINTALLY_TELEMETRY=0`)
- [x] `/health` returns only `{"status", "version"}`
- [x] `edge.py`, `export-edge`, `benchmark-edge` deleted
- [x] Forecast / TabPFN deleted (MAE 3.79 vs 3.21 for cooking confirmed orders)
- [x] KDS station, BOM, ROI, economics deleted
- [x] `eval` no longer writes RESULTS.md; `NOT RUN` replaces 0.0%
- Gate: `92 passed`, ruff clean, `git status` clean after pytest.
