# AGENTS.md — TiffinTally engineering guidance

This is the canonical shared engineering guidance for this repository. It applies to any
coding agent or human contributor working here, in any checkout or worktree.

If a tool needs its own instruction file, point it at this one rather than duplicating
these rules. Do not restate them elsewhere — two copies of a policy is zero policies.

---

## 1. What this product is

TiffinTally turns a pasted WhatsApp group-chat export from a home tiffin kitchen into two
artefacts that share one daily policy:

- a **prep sheet** (what to cook, packed and labelled), and
- a **dues ledger** (who owes what, with chat payment messages held as *claims* until the
  cook confirms receipt).

Customers write in Hinglish, late at night. Order, cancellation, pause and modification
messages are interleaved with complaints and chatter, so recognising *which* messages are
orders is the actual difficulty. See `README.md` for the product overview and
`docs/PRODUCTION_ARCHITECTURE.md` for the design.

## 2. Repository map

| Path | Purpose |
| --- | --- |
| `tiffintally/app.py` | FastAPI app, HTML views, JSON API, session handling |
| `tiffintally/parser.py`, `reconcile.py`, `schema.py` | chat parsing, daily policy, types |
| `tiffintally/extract/` | extraction backends: rules, hosted Gemma, Modal, OpenAI-compatible |
| `tiffintally/privacy.py`, `security.py`, `uploads.py` | PII masking, guardrails, size caps |
| `tiffintally/db.py`, `telemetry.py`, `logging_config.py` | persistence and forensics |
| `tests/` | pytest suite; `tests/probes/` holds offline regression probes |
| `scripts/` | eval harness, claim registry checks, leakage and publish gates |
| `evals/` | frozen evaluation splits and saved predictions |
| `docs/` | architecture, decisions, evidence notes. `docs/planning/` and `docs/review/` are working notes, not evidence |

## 3. Commands

```bash
uv sync --all-extras --dev          # install
uv run tiffintally serve            # local server
uv run pytest -q                    # full suite
uv run pytest tests/probes -v       # offline regression probes
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_claims.py            # numerical claims registry
uv run python scripts/leakage_report.py --check-known
```

CI (`.github/workflows/ci.yml`) runs all of the above on every PR and push to `main`.
Never leave a gate red that you could have run locally.

**CI must never call a hosted model.** `EXTRACTOR_BACKEND: "off"` and
`TIFFINTALLY_TELEMETRY: "0"` are set for a reason: a hosted call in CI spent GPU credit
on every push. Do not remove them.

## 4. Preserve ongoing work

This repository is worked on by **more than one agent concurrently, sharing one checkout**.

- Run `git status` and `git log --oneline -5` **before** you edit, commit, merge or rebase.
- **Never discard another agent's work.** No `git reset --hard`, `git checkout -- .`,
  `git clean`, `git stash drop`, or force-push over someone's branch. Uncommitted changes
  in this tree may belong to a session that is still running.
- Do not modify another agent's branch or worktree without saying so and getting agreement.
- Stay on the branch you were given. Create a topic branch for a change; do not commit to
  `main` directly and do not switch branches out from under a running session.
- Prefer minimal, compatible changes. Read the surrounding code before editing it.
- If you find uncommitted work you did not create, **leave it alone and report it**.

## 5. Engineering quality

- Build maintainable, production-quality functionality, not sketches. No dead code, no
  commented-out blocks, no `TODO` left in a merged path.
- Preserve application reliability and backward compatibility. Existing endpoints,
  response shapes, CSV columns and CLI flags are contracts.
- Write the tests with the change: unit tests for logic, integration tests for routes and
  persistence. A new endpoint without a test is unfinished.
- Handle meaningful errors and edge cases. Never swallow an exception into a silent
  fallback that then looks like success.
- Validate before you claim: run the focused test, then the full gate, and say which
  command produced which result.
- Keep secrets out of source control. `.env` is never committed; `.env.example` holds
  placeholder keys only; `gitleaks` runs in CI.
- Record permanent technical decisions in `docs/DECISIONS.md`.

## 6. Honest evidence

This project holds itself to a stricter evidence rule than most. Keep it.

- Never publish a number that was not measured, and never present a rules-only or
  unexecuted run as a model result. `RESULTS.md` records `NOT RUN` rather than a fake
  percentage — that is the standard, not an oversight.
- Record **what actually answered** (backend, served model, fallback), not what was
  configured.
- Known data leakage, synthetic-data caveats and withheld evidence live in
  `docs/KNOWN_LEAKS.md`, `docs/POLICY.md`, `docs/NUMBERS.md` and `docs/CLAIMS.md`.
  Do not quietly delete a caveat to make a result look better.
- Unverifiable claims belong in `docs/QUESTIONS.md`, not in `README.md` or a post.

## 7. Automated pull-request testing

Meaningful product changes are verified by an automated test run against a **real
deployment of the PR's own code**, not by unit tests alone.

1. Define acceptance criteria before you implement.
2. Implement the change **and** its unit/integration tests.
3. Run the local gates from §3.
4. Open a focused PR. Keep it to one concern.
5. Confirm the PR's preview deployment reports ready and the URL actually loads.
6. Let the automated PR test run execute on its own — do not paste unit-test output as if
   it were that run.
7. Read the actual run results. Fix real failures at their root cause.
8. Push the fix, confirm the run re-executes, and keep the passing run as regression
   evidence.

**Never** fabricate success, weaken a genuine assertion, or disable a check to turn a PR
green. A red test you understood is worth more than a green one you engineered.
If a run cannot execute for an environmental reason, say that plainly.

## 8. Product-first priorities

- Fix release-blocking reliability and correctness before optional feature work.
- Choose features from the real roadmap in `README.md` / `docs/PRODUCTION_ARCHITECTURE.md`.
  Prefer a change that satisfies several genuine requirements at once.
- Do not build a feature whose only purpose is to be demonstrated.
- **The product's identity is its own.** Do not brand the application, its UI, its docs
  or its architecture around a third-party service, an event, a submission or a judging
  rubric. Integrating a third-party tool is a normal engineering decision and is described
  as one.
- Track cross-session status in `docs/DEVELOPMENT_HANDOFF.md`. Update it when a milestone
  meaningfully changes.

## 9. Re-read this before you plan

Before planning a substantial feature, changing shared infrastructure, or opening a PR:

- re-read this file and `docs/DEVELOPMENT_HANDOFF.md` **in the current checkout**, and
- do not assume instructions remembered from an earlier session are still true.

Context windows and branches drift. Re-reading is cheap; acting on stale guidance is not.

## 10. Deployment

`render.yaml` describes the production web service; the live URL is recorded in
`README.md` and `docs/DEVELOPMENT_HANDOFF.md`. Preview deployments for pull requests are
created by `.github/workflows/preview.yml`. Deployment notes and their honest status are
in `docs/DEPLOY.md` — if something is not actually deployed, keep saying so there.