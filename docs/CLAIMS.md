# Current claims

Generated from implementation and local evidence; not production certification.

| Claim | Implementation | Source evidence | Last verified SHA |
|---|---|---|---|
| Primary identity comes from the source sender | tiffintally/extract/gemma.py:464 | tests/test_modal_integration.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Payments need eligible session confirmation | tiffintally/reconcile.py:652 | tests/test_modal_integration.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Duplicate source payments are credited once | tiffintally/reconcile.py:655 | tests/test_modal_integration.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Token maps default to instance memory | tiffintally/privacy.py:65 | tests/test_round4_privacy.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Sheet and ledger share daily replay | tiffintally/reconcile.py:292 | tests/test_daily_invariants.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Session creation has a hard cap | tiffintally/app.py:123 | tests/test_session_cap.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Private holdouts require provenance and freezing | tiffintally/datasets.py:52 | tests/test_human_holdout.py | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Numerical tables rescore saved predictions | scripts/publish_results.py:35 | evals/final/public_summary.json | 76acb4833e8b40b68a8fb977d8d598682f08574a |
| Hosted default is a Gemma 4 id the Gemini API serves | tiffintally/extract/gemma.py:32 | tests/test_gemma_transport.py | pending: fix/honest-final |
| A Gemini answer with a thought part or a fence is still parsed | tiffintally/extract/gemma.py:74 | tests/test_gemma_transport.py | pending: fix/honest-final |
| A retired model id shows "rules (regex)" plus the HTTP error | tiffintally/extract/gemma.py:392 | tests/test_gemma_transport.py | pending: fix/honest-final |
