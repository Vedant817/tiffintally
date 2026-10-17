# Development handoff

A short, factual status board for anyone (or any agent) picking up this repository.
Last updated **2026-10-17**, by the session that added the deployment and PR-testing
pipeline.

This file tracks **engineering** state only. Anything event- or submission-specific is
deliberately kept out of this repository.

---

## 1. Current product milestone

TiffinTally is a working, deployed product: paste a WhatsApp group export, get a prep
sheet and a matching dues ledger built on one shared daily policy. Order/cancel/pause
detection from Hinglish chatter, PII masking before any hosted model is called, and
payment claims held until the cook confirms receipt.

The milestone that is *not* done is evidentiary honesty work: separating what was
actually measured from what was assumed, and making the remaining gaps explicit rather
than papering over them. See `RESULTS.md`, `docs/KNOWN_LEAKS.md`, `docs/NUMBERS.md`.

## 2. Implementation progress

| Area | State |
| --- | --- |
| Chat parsing and daily policy | Implemented, covered by unit + Hypothesis invariant tests |
| Extraction backends (rules, hosted Gemma, Modal, OpenAI-compatible) | Implemented; backend selection is reported, never silently substituted |
| Reconciliation, prep sheet, ledger, balances CSV | Implemented |
| Privacy masking and persistence gating | Implemented, red-team tested |
| Benchmarks, scoring, eval harness | Implemented; offline rules-only numbers published |
| Telemetry and forensic failure logging | Implemented |
| Production deployment | **Live** (see §4) |
| CI gates on every PR and push | **Active** (`.github/workflows/ci.yml`) |
| PR preview deployment | **Active** (`.github/workflows/preview.yml`) |

## 3. Active branches and work areas

> Re-check with `git status` and `git worktree list` before assuming this table is current.

| Branch | Owner | Work area |
| --- | --- | --- |
| `main` | shared | Integration branch. All PRs target this. |
| `fix/honest-final` | concurrent session | Hosted-extraction correctness (model selection, response parsing). **Do not edit.** |
| `chore/pr-preview-testing` | integration session | Deployment, PR previews, shared agent guidance, TestSprite readiness. |

More than one agent works this repository at a time. `AGENTS.md` §4 is binding: inspect
Git state first, never discard uncommitted work, never touch another session's branch.

## 4. Deployment and test readiness

**Production**

- Live URL: <https://tiffintally-lbn2.onrender.com>
- `GET /health` → `200 {"status":"ok","version":"0.1.0"}`
- Render service `tiffintally` (free plan, region `oregon`), auto-deploy on `main`.
- Runs in demo mode: sheets and payment confirmations are held in ephemeral per-session
  memory and are never written to disk. `TIFFINTALLY_PERSIST=0`.
- No hosted-model key is configured on the service, so the demo answers with the local
  rules path and the UI reports that honestly. Adding a key is a one-step human action
  and is listed in `HUMAN_TODO.md`.

**Pull-request previews**

- `.github/workflows/preview.yml` creates one Render service per open PR
  (`tiffintally-pr-<number>`), waits for it to go live *and* answer `200` on `/health`,
  then registers it as a GitHub deployment and comments the URL on the PR.
- Preview services are deleted when the PR closes, because free-tier service slots are
  limited.
- Required repository configuration: secret `RENDER_API_KEY`, variable
  `RENDER_WORKSPACE_ID`.

**Local gates** (all must pass before a PR)

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run pytest tests/probes -v
uv run python scripts/check_claims.py
uv run python scripts/leakage_report.py --check-known
```

**Automated PR testing (TestSprite 3.0)**

| Item | State |
| --- | --- |
| Live HTTPS deployment reachable | Done |
| Deployment-ready signal per PR (GitHub deployment + status + bot comment) | Done |
| TestSprite workspace + GitHub App installed on this repo | **Not done — needs a human** |
| TestSprite project created and linked to this repo | **Not done — needs a human** |
| Test suite generated against the live URL | **Not done — needs a human** |
| Pull Request trigger configured and active | **Not done — needs a human** |
| PR observed carrying a real TestSprite comment | **Not done — needs a human** |

The remaining steps are all inside the TestSprite web portal and all require an
authenticated session, so they cannot be completed from here. The exact click-path is in
`docs/TESTSPRITE_SETUP.md`. Everything they depend on is live.

## 5. Outstanding engineering blockers

1. **No hosted model key in the deployed demo.** The demo runs the rules path. Supply a
   key through Render environment variables to exercise the hosted path in production.
2. **No custom domain.** The app serves on the `onrender.com` subdomain. A domain can be
   attached in Render; DNS records live with the domain owner.
3. **Evidence gaps are open, by design.** Human-written holdout labels, independent
   re-labelling, and cost measurement are still not done. They are tracked in
   `HUMAN_TODO.md` and `docs/QUESTIONS.md`. Do not close them by assertion.
4. **Free-tier preview concurrency.** Preview services consume the workspace's free
   service slots. Several PRs open at once can exhaust them; the workflow fails loudly
   rather than silently skipping a deployment.

## 6. Integration dependencies

- **Render** — hosts the production service and the per-PR previews. Needs
  `RENDER_API_KEY` in repository secrets and `RENDER_WORKSPACE_ID` in repository variables.
- **GitHub deployment events** — the signal automated PR testing listens for. Produced by
  `preview.yml`; do not remove it in favour of a platform preview button without
  confirming the replacement emits the same event.
- **A hosted model endpoint** — optional. Absent, the app degrades to the rules path and
  says so.
- **SQLite** — opt-in only, behind `TIFFINTALLY_PERSIST=1`. Not used in the demo.

## 7. Next recommended product tasks

Ordered by product value, not by tooling convenience:

1. Take a real cook session end-to-end with a consented export and fix whatever breaks.
   This is the only unimplemented thing that matters more than it is worth documenting.
2. Close the human-holdout evidence gap described in `HUMAN_TODO.md`.
3. Export/import a single chat cleanly, so carrying a balance between sessions stops
   being manual CSV work.
4. Measure and publish cost per sheet, once there is a key to measure against.
5. Review and replace any extraction rule that a failing case justifies removing.

## 8. Verified PR-testing status

As of the last update:

- Production deployment verified reachable over HTTPS — **externally verified**.
- PR preview deployment pipeline — **implemented and exercised end-to-end**; see the PR
  that introduced it for the recorded run.
- TestSprite execution on a PR — **not yet performed** (blocked on portal authorisation,
  §4). No TestSprite result is claimed anywhere in this repository.

## 9. Update protocol

Update this file when a milestone meaningfully changes: a deployment goes live or moves,
a blocker clears, a branch appears or retires, or the verified PR-testing status changes.
Keep it factual and short. If a claim here cannot be checked, it does not belong here.

**Last updated:** 2026-10-17 · **Updated by:** integration session (deployment + PR testing)