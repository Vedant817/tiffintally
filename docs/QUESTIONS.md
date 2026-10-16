# Open questions and blocked gates

Updated 16 Oct 2026, after the round-3 fix pass. See
`docs/planning/FIX_PROMPT3.md` for the brief and `docs/review/AUDIT3.md` for the
review that prompted it.

## [HUMAN] Stop the public Modal endpoint (urgent, security)

`scripts/modal_serve.py` now requires `Authorization: Bearer <token>` from a
Modal secret and answers 401 without it. **The deployed app is still the old
unauthenticated one.** Until it is redeployed or stopped, anyone who read the
repo can spend GPU credit on it.

    uv run modal app stop tiffintally-extract     # or redeploy with the token

Then, to bring it back:

    uv run modal secret create tiffintally-extract-token   # interactive
    uv run modal deploy scripts/modal_serve.py
    export MODAL_EXTRACTOR_URL=<printed url>
    export MODAL_EXTRACTOR_TOKEN=<same value as the secret>

Two notes learned the hard way. `modal deploy` can report "no changes detected"
while an old warm container still serves the old code, so stop the app first.
And the URL Modal prints ends in `-api.<region>.modal.run`; the app URL without
that suffix answers 404, which is indistinguishable from a dead model.

## [HUMAN] Re-measure the model after the batching fix

The 78.0% / 88.0% figures in `RESULTS.md` were measured on the old client, which
re-parsed the whole batch reply once per message. The Gemini path is fixed and
tested, but **the model has not been re-run since**. The Modal path returned a
positional list and was never affected by the multiplication bug.

So: re-run `scripts/head_to_head.py` against the deployed endpoint before those
numbers go in the post. Until then they describe the previous code.

## [HUMAN] Backend selection

Per Vedant's instruction the fine-tuned Modal endpoint is the project's backend,
not an experiment. `EXTRACTOR_BACKEND` auto-selects:

1. `modal` when both `MODAL_EXTRACTOR_URL` and `MODAL_EXTRACTOR_TOKEN` are set
2. `gemini` when `GOOGLE_API_KEY` is set
3. `off` (rules only) otherwise

Exporting the two Modal variables is all that is needed; no Google AI Studio key
is a prerequisite. The test suite and CI force `EXTRACTOR_BACKEND=off`, so no
test can make a network call.

The Gemini path is kept as a fallback. It is no longer the default, which was
the audit's recommendation.

## [HUMAN] Unchanged from the audit

- Render deploy. Service name must not be `tiffintally`; that subdomain belongs
  to a different product. `render.yaml` still needs its demo-mode work.
- `.tech` domain, screen recording, first real cook, DEV post publish.
- 30-50 real cook messages via `scripts/label_cli.py`. `data/private/real_test.jsonl`
  has 50 rows but no `collected_from_cook` marker, so it is machine-generated
  despite `is_synthetic: false`.

## Decisions taken without asking

**Restatements are applied, not withheld.** Two different counts from one name
for one meal on one day is either a customer correcting herself or two people
saved under one display name, and the text cannot tell them apart. The later
message is applied and flagged `restated` for review. Withholding both, which is
what the conflict check did, made a re-stated order print an empty sheet.

**A Google key is not needed.** The audit recommended Gemini as the default
because Modal was slow and unreliable. The project decision is to serve the
fine-tuned model and own that cost.

**Licence.** The audit's claim was correct and was verified against the Hugging
Face API rather than from memory: `Qwen/Qwen2.5-3B-Instruct` reports
`license: other`, `license_name: qwen-research`, non-commercial, with a duty to
display "Built with Qwen". The earlier "Apache-2.0" line in `modal_serve.py` was
wrong. Consequence: this adapter cannot be the basis of a paid product, and the
post must not imply otherwise.

## Known gaps

- The adapter is on a private Modal volume and is published nowhere a judge can
  fetch it, so "reproducible" is not a claim this repo makes yet.
- `RESULTS.md` is hand-written from saved runs and is never regenerated. CI fails
  if `tiffintally eval` changes it. A hand-written file can drift from the runs;
  the CI check only catches regeneration, not drift.
- No test exercises `scripts/modal_serve.py`'s HTTP layer end to end. The parser
  is unit-tested; the auth and batching glue are not, because deploying to test
  it costs GPU credit.