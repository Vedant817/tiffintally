# Final QA, branch fix/honest-final

Run on 17 October 2026 from a fresh clone of the branch, not from the working copy:

```
git clone --branch fix/honest-final https://github.com/Vedant817/tiffintally.git qa-tiffintally
cd qa-tiffintally
uv sync --all-extras --dev
```

Clone HEAD: `cb21601`. Nothing below was copied from the working tree.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Lint | `uv run ruff check .` | PASS: All checks passed! |
| Format | `uv run ruff format --check .` | PASS: 121 files already formatted |
| Tests | `uv run pytest -q` | PASS: **328 passed, 4 xfailed, 1 warning in 19.72s** |
| Claims registry | `uv run python scripts/check_claims.py` | PASS: source-backed current claims; historical entries remain unverified |
| Public tables | `uv run python scripts/publish_results.py --check` | PASS: public tables match saved predictions |

The 4 `xfailed` are the intentional T4-002 xfails; the same command on `main` at `1cf2a21`
reported 305 passed, 4 xfailed.

## Running server

```
EXTRACTOR_BACKEND=off uv run tiffintally serve --port 8123
```

| Request | Command | Result |
|---|---|---|
| `GET /health` | `Invoke-WebRequest http://127.0.0.1:8123/health` | 200 |
| `GET /` | `Invoke-WebRequest http://127.0.0.1:8123/` | 200 |
| `GET /benchmarks` | `Invoke-WebRequest http://127.0.0.1:8123/benchmarks` | 200 |
| `POST /process` | `Invoke-WebRequest -Method Post -Body @{raw_text=<demo sample paste>; target_date="tomorrow"}` | 200 |

The paste used the five messages from `tiffintally/demo_sample.json` in Android export form:

```
17/10/2026, 8:00 pm - Ravi: Aunty, tomorrow lunch 2 for our desk; pack the bag together.
17/10/2026, 8:01 pm - Priya: For tomorrow please keep lunch 1, aaj roti nahi rice in that box.
17/10/2026, 8:02 pm - Karan: Tomorrow lunch 2 plates in total, roommate Tanvi ke liye ek in that bag.
17/10/2026, 8:03 pm - Pooja: Tomorrow lunch 2 in the blue carrier, no onion please.
17/10/2026, 8:04 pm - Vikram: Week ka hisaab: 11,500 paid through GPay, receipt bheja.
```

Banner text returned in that response, verbatim:

```
Rules (regex) only. No model was called for this sheet, so every count below came from
the pattern rules, not from a model.
EXTRACTOR_BACKEND=off, rules only
```

`GET /prep` in the same session: "total 7 thalis ... Lunch ke 7 orders hain", with the
per-customer mods for Pooja and Priya. `GET /ledger` in the same session: "Vikram:
11500.0 claimed, not confirmed." Both match the expectations already pinned in
`tests/test_demo_sample.py`.

## Hosted Gemma path, no key present

```
EXTRACTOR_BACKEND=gemini uv run tiffintally serve --port 8124
POST /process   (GOOGLE_API_KEY is not set in this environment)
```

Response 200, and the banner was:

```
Rules (regex) only. No model was called for this sheet, ...
GOOGLE_API_KEY is not set
```

So the app does not claim Gemma ran when it cannot run. **NOT DONE: the one POST with a
real key.** No `GOOGLE_API_KEY` exists in this environment (checked in the process,
user and machine scopes, and there is no `.env`), so no Gemma row was measured and
`evals/final/baselines/gemini/test.jsonl` does not exist. `RESULTS.md` says
"Gemma baseline: NOT RUN (no GOOGLE_API_KEY in the environment)". `HUMAN_TODO.md` carries
the exact command to run it later.

## Regression and grep checks

| Check | Command | Result |
|---|---|---|
| Persistence leak | `uv run pytest tests/test_db_persistence.py -q` | PASS: 7 passed |
| Retired model ids | `git grep -n "gemma-2-9b-it\|gemma-3" -- . ':!docs/review' ':!docs/planning' ':!evals/retracted'` | Two hits, both in `tests/test_gemma_transport.py`: one asserts the default is not that id, the other fakes its 404. No default, doc or config names it. |
| Scorer-demo wording | `Select-String -Path README.md,post.md -Pattern "self-heal" -CaseSensitive:$false` | No hits |
| Post wording | `Select-String -Path post.md -Pattern "hallucinat\|high fidelity\|JSON schema generation\|zero-cost\|305 tests\|collaborative browser\|One-Click Deploy\|NEGATED_CANCELLATION\|SPLIT_ROOMMATE\|cd tiffin-tally"` | No hits |
| Post numbers | `Select-String -Path post.md -Pattern "\d+(\.\d+)?%"` | No hits, so every number in the post is a count from `RESULTS.md`, from this pytest run, or a date |
| Blueprint | `uv run python -c "import yaml;print(yaml.safe_load(open('render.yaml')))"` and `Select-String -Path render.yaml -Pattern "gemma-2"` | Parses; `runtime: python`, `EXTRACTOR_BACKEND` sync false; no `gemma-2` |
| Deploy guide | `Select-String -Path docs/DEPLOY.md -Pattern "TABPFN\|TINKER\|ELEVENLABS"` | No hits |

## Preview deployment of this branch

`preview.yml` deployed this branch's own commit to its own service, and the checks on the pull
request report it live. Verified by hand against that URL, not copied from the job log:

```
GET  https://tiffintally-pr-2.onrender.com/health     -> 200 {"status":"ok","version":"0.1.0"}
GET  https://tiffintally-pr-2.onrender.com/            -> 200
GET  https://tiffintally-pr-2.onrender.com/benchmarks  -> 200
POST https://tiffintally-pr-2.onrender.com/process     -> 200, banner "Rules (regex) only. No model was called for this sheet."
```

The difference that matters: production (<https://tiffintally-lbn2.onrender.com>) still serves
`main`, so its `/benchmarks` is titled "AI Benchmark & Self-Healing Lab". The preview of this
branch is titled "Scorer Demo & Repair Rules | TiffinTally", which is the wording this branch
fixes. The fix is therefore verified on a real deployment of this branch's code, and the reason
to merge before recording any demo is now measured rather than argued.

No model key is configured on the preview either, so the preview answers with the rules path and
says so. That is the same honest behaviour production shows.

## Production deployment, checked after the QA run

The QA run above happened before any deployment existed. One is now live, so this
section supersedes the deployment line in "Not done". Checked with:

```
Invoke-WebRequest https://tiffintally-lbn2.onrender.com/health      -> 200 {"status":"ok","version":"0.1.0"}
Invoke-WebRequest https://tiffintally-lbn2.onrender.com/             -> 200
Invoke-WebRequest https://tiffintally-lbn2.onrender.com/benchmarks   -> 200
POST https://tiffintally-lbn2.onrender.com/process                  -> 200
```

Two things that URL is, and is not:

- It serves **`main`**, which does not contain this branch. Its `/benchmarks` still reads
  "AI Benchmark & Self-Healing Lab" and "Run Benchmark & Self-Healing Loop", because the
  wording fixed in this branch (`1768909`) is not merged. Verified: the live page returns
  those strings today. Anyone recording a demo against the live URL before this branch
  merges will capture the copy this branch removes.
- Its `POST /process` banner reads "Rules (regex) only. No model was called for this
  sheet", because no key is configured on the service. That is the honest behaviour, and it
  is what `post.md` describes for a no-keys run.

## CI on this branch

Run `39041426504`, head `60c3b14`: both jobs green, every step successful.

| Job | Steps |
|---|---|
| `test` | lint, format, tests, regression probes, claims registry, known leakage, saved-prediction rescore, daily invariants, secret scan: all success |
| `no-results-drift` | `tiffintally eval` leaves `RESULTS.md` untouched: success |

Four earlier runs failed at `Verify no secret leakage` only. The cause was not a finding:
`gitleaks/gitleaks-action@v2` refuses to scan a `pull_request` event without a token, so the
scan never started and every pull request in the repository failed that step. The fix is
`GITHUB_TOKEN` on the step plus `pull-requests: read` in `permissions`, and the scan now runs
for real: that step's log reads `13 commits scanned` and `no leaks found`.

The same fix also exists on `chore/pr-preview-testing`; it is applied here too so this branch
can be verified on its own instead of depending on merge order. `EXTRACTOR_BACKEND` in
`render.yaml` is still outstanding and is owned by that PR.

Greptile posted one comment on this pull request: its trial ended, so it performed no review.
There is no review feedback to act on. Reactivating it is an account action on the owner's
side, not a repository change.

## Not done

- **NOT DONE: Gemma measurement.** No key in the environment. Nothing in the repository
  claims a Gemma number, so no number is missing.
- **NOT DONE: one end-to-end POST with a real key.** Needs `GOOGLE_API_KEY`. Until it is
  run, the Best Use of Gemma line in `post.md` must stay deleted.
- **NOT DONE: a live URL serving this branch.** Production serves `main` (§ above). The
  Best Use of Render condition in `post.md` asks for a live URL serving the app at the time
  of publishing, so it needs this branch merged and auto-deployed first. Which prize
  categories to enter is Vedant's call, not this branch's; both bracketed lines are left
  untouched.
- **NOT DONE: a human cook has not used this.** `post.md` says so in the first section.
- **NOT DONE: post-deadline commit list.** `README.md` has the empty list the challenge
  asks for. Nothing goes in it before 19 Oct 12:29 PM IST, and `docs/FINAL_QA.md` plus the
  branch itself are the first commits that would need listing if they land after that.

## Human-only, not attempted here

Merging the PR, publishing the DEV post, the screenshot, the screen recording, the Render
deploy, and choosing prize categories.