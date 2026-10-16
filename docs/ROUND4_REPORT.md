# Round-four technical report

The review branch repairs model-field loss and sender attribution, makes payment
credits explicit and idempotent, shares pure daily replay between sheet and ledger,
uses exact money, removes test-fitted dietary literals, and records complete cleaned
rule predictions under the shared scorer. Privacy maps now default to memory,
normalized names are masked before transport, and sessions have a hard cap.
This is a technical repair with local evidence, not submission or production signoff.

## Finding disposition

Fixed means the reported path has a regression and passed local checks. It does
not certify the deployed service. Partly marks remaining data, protocol or tooling
requirements explicitly; those are not hidden by the green suite.

| Finding | Status | Commit | Test or evidence |
|---|---|---|---|
| T4-001 | partly: regex reproducible; historical model rows absent | 72a9308, c0c5586 | test_frozen_predictions_rescore_bit_for_bit; model statuses NOT RUN |
| T4-002 | fixed: removed active test-fitted literals | 1c421c7 | test_canonical_phrases_have_development_evidence; strict expected failures retained |
| T4-003 | partly: independent scorer and dev labels; legacy gold remains frozen | 1c421c7, c0c5586 | test_event_sets_are_order_independent_and_mods_are_sets; human holdout pending |
| T4-004 | fixed: all schema fields survive; invalid rows reach review | 03d0935 | test_real_server_parser_preserves_all_fields; test_demo_lunch_seven_and_claimed_payment |
| T4-005 | fixed: source sender wins; secondary requires source support | 03d0935, 76acb48 | test_real_modal_client_sender_and_secondary_and_money; token-like sender regression |
| T4-006 | fixed: calendar day per source message | 828bff4 | test_ten_evenings_bill_twenty_plates |
| T4-007 | fixed: pure shared replay, identical cutoff policy | 828bff4 | test_call_order_cannot_change_events_or_bill; test_sheet_equals_daily_ledger |
| T4-008 | partly: known leakage reported; new dev is synthetic development | c0c5586 | docs/KNOWN_LEAKS.md; leakage.json; human holdout pending |
| T4-009 | fixed: claims need eligible confirmation; duplicate and raw-input bypasses closed | 03d0935, 99d78e4, 76acb48 | tests/test_injection.py; duplicate payment and direct-parser regressions |
| T4-010 | fixed: event-set scorer, field accuracies named accurately | c0c5586 | tests/test_scoring.py; saved predictions; shared training scorer |
| T4-011 | partly: recipe designed, not trained; proposed labels need review | 99d78e4 | TRAINING_RECIPE_V2.md; relabel_v2.jsonl |
| T4-012 | partly: offline harness; hosted comparisons and custom-prompt contract absent | 99d78e4 | baseline status files; ML_DECISIONS.md |
| T4-013 | partly: documented extraction cases repaired; original probe sources unavailable | 1c421c7 | tests/probes/test_round4_extract.py |
| T4-014 | fixed: new sample and date-clause regression | 1c421c7 | tests/test_demo_sample.py on rules and mock transport |
| T4-015 | partly: total/share convention fixed; relabel overlay is proposed, not approved gold | 828bff4 | test_secondary_share_is_part_of_total; relabel_v2.jsonl |
| T4-016 | fixed: Decimal, session price, balance CSV | 828bff4 | exact-paise, opening-only and CSV/alias integration tests |
| T4-017 | fixed in web path: isolated maps and explicit masking limits | 76acb48 | tests/test_round4_privacy.py; pre-existing ignored map retained for owner cleanup |
| T4-018 | fixed: suggestions require cook confirmation | 828bff4 | test_balance_csv_and_explicit_alias_confirmation |
| T4-019 | fixed in scoped docs; historical Gemini diagnosis corrected | c0c5586, 76acb48 | QUESTIONS.md, CLAIMS.md, generated public tables; submission draft untouched |
| T4-020 | partly: new regressions and CI gates; original auditor suite missing | dd3b9d4, c0c5586, 76acb48 | evidence/final-qa.md; tests/probes/README.md |
| T4-021 | fixed: retired Tinker, duplicate evaluators/renderers and old sweep | 76acb48 | retired-backend test; active scorer imports |
| T4-022 | fixed: dependency bounds, lock and unused dependency removal | 76acb48 | fresh-clone uv sync output |
| T4-023 | fixed: hard session cap with least-recently-used eviction | 76acb48 | test_active_sessions_cannot_exceed_cap |
| T4-024 | fixed: health follows package metadata | 76acb48 | test_health_uses_installed_project_version |
| T4-025 | fixed: obsolete training-text edge score retired | 76acb48 | no training-text edge pass metric in active training runner |
| T4-026 | partly: local latency saved; hosted/cold latency and billing not measured | 9532f00 | evals/final/latency.json; no GPU permission |

## Honest numbers

The generated table and source pointers are in [NUMBERS.md](NUMBERS.md),
[RESULTS.md](../RESULTS.md), and `evals/final/public_summary.json`. These describe
synthetic rows with known label and sibling-template limits. The original adapter
aggregates cannot be reconstructed into complete predictions. The old apparent
run-to-run variance is neither reproduced nor disproved by an offline regex run.
The offline hybrid is explicitly incomplete and makes no model-performance claim.

## Final QA questions

- **Is the accuracy valid?** The new cleaned-rule event-set scores rescore from all
  saved predictions. They apply to this synthetic file only. Real-message accuracy
  and model superiority are unknown. See scoring.py and the saved prediction paths.
- **Is anything faked?** No canned production output was added. Mock replies occur
  only in explicitly named tests. Hosted comparisons and training are NOT RUN.
- **Is anything hardcoded?** The baseline is still deterministic domain rules.
  Active modifier phrases have development evidence; the reported test-only rules
  were removed. That does not turn the consumed legacy test into a new holdout.
- **Is the baseline fair?** It is now inspectable with test-only literals removed;
  the legacy benchmark remains contaminated, and there is no complete paired
  few-shot/base/adapter comparison. A fine-tuning value claim is unsupported.
- **Is there leakage?** Yes. The saved report documents a same-label sibling pair
  beyond the configured threshold. Legacy dev is part of train. CI's known-leak
  check reproduces this limitation; it does not certify a clean split.
- **What can honestly be claimed?** The saved synthetic results describe the
  cleaned rules only; they establish neither model superiority nor accuracy on
  real cook messages. Wilson row intervals do not adjust for template dependence.

## Remaining gates and scope

See [HUMAN_TODO.md](../HUMAN_TODO.md): original probes, consented blind human labels
and repeat-label agreement, explicit GPU permission if desired, licence choice,
endpoint authentication/redeployment by the owner, and branch/policy review.
The few-shot endpoint contract and verified adapter/decoding metadata remain
technical follow-up before a hosted comparison can be certified. No inference,
training, deployment, domain, video or post publication was performed.

The legacy frozen files, old result directories and retracted artifacts are
preserved. The old ignored local privacy database is no longer used but was not
deleted because the brief prohibits deleting pre-existing data. Root copies of
the supplied audit and prompt remain user inputs; canonical copies are committed
under docs/review and docs/planning.

The independent read-only security review reproduced duplicate payment credit,
Unicode-name masking and a direct-parser money bypass. Regressions now exercise
those paths through the repaired sink. Full command output is in
`evidence/final-qa.md`; machine-readable counts and the audited SHA are in
`evals/final/qa_summary.json`. Local Windows checks are not hosted Linux CI proof.
