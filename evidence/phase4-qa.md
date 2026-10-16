# phase4: clean-clone QA

Clone: `C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-l3ryut69\repo`

Original auditor probe sources: NOT SUPPLIED. Reconstructed probes are identified in tests/probes/README.md.

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe check .

```text
All checks passed!

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe format --check .

```text
118 files already formatted

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest -q

```text
..................................................................x.x.xx [ 28%]
........................................................................ [ 56%]
........................................................................ [ 85%]
......................................                                   [100%]
============================== warnings summary ===============================
tests\test_app.py:3
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-l3ryut69\repo\tests\test_app.py:3: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
250 passed, 4 xfailed, 1 warning in 8.93s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/check_claims.py

```text
PASS: source-backed current claims; historical entries remain unverified

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m tiffintally.cli eval --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-l3ryut69\offline-eval

```text
Running comprehensive TiffinTally evaluations...
{
    'regex': {
        'n': 50,
        'strict': {
            'hits': 35,
            'accuracy': 0.7,
            'wilson_95': [0.562496495355466, 0.8089644649911906]
        },
        'lenient': {
            'hits': 47,
            'accuracy': 0.94,
            'wilson_95': [0.8378290831116182, 0.979385029651026]
        },
        'chitchat': {'n': 2, 'strict_hits': 2},
        'intent': {'n': 48, 'strict_hits': 33},
        'metadata': {
            'system': 'regex',
            'code_sha': 'e7338073bf586ed4d1fc07d03684746fe5306f9c',
            'prompt_sha256': 
'7e9e1c1ec8d9e6535abedb695bef6dccfc0d65906b77e308f8ab6b6669aeed42',
            'adapter_id': None,
            'adapter_sha': None,
            'max_new_tokens': None,
            'batch_size': 1,
            'dtype': None,
            'decoding': 'deterministic rules',
            'n': 50,
            'date': '2026-10-16T11:16:34.595301+00:00',
            'source': 
'C:/Users/vedan/AppData/Local/Temp/tiffintally-qa-l3ryut69/offline-eval/regex/t
est.jsonl'
        }
    },
    'model': 'NOT RUN (needs approval)',
    'cost': 'NOT MEASURED',
    'human_holdout': "NOT RUN: [Errno 2] No such file or directory: 
'data\\\\private\\\\real_test.jsonl'"
}
Saved per-row predictions and summary under 
C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-l3ryut69\offline-eval

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/leakage_report.py --check-known

```text
Known leakage exactly reproduced; not a clean-split certification.

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/compare.py evals/final/regex/test.jsonl evals/final/regex/test.jsonl

```text
{"n": 50, "templates": 36, "exact_mcnemar_p": 1.0, "template_clustered_95": [0.0, 0.0], "conclusion": "No superiority claim is supported."}

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/publish_results.py --check

```text
PASS: public tables match saved predictions

```

Executed checks: PASS

This is a separate QA pass by the same agent, not an independent human review. Missing original probes and human acceptance items are not certified by these commands.
