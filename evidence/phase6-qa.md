# phase6: clean-clone QA

Clone: `C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\repo`

Original auditor probe sources: NOT SUPPLIED. Reconstructed probes are identified in tests/probes/README.md.

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe check .

```text
All checks passed!

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe format --check .

```text
125 files already formatted

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest -q

```text
........................................................................ [ 24%]
............................x.x.xx...................................... [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
.........                                                                [100%]
============================== warnings summary ===============================
tests\test_app.py:3
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\repo\tests\test_app.py:3: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
293 passed, 4 xfailed, 1 warning in 6.96s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/check_claims.py

```text
PASS: source-backed current claims; historical entries remain unverified

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m tiffintally.cli eval --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\offline-eval

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
            'code_sha': '76acb4833e8b40b68a8fb977d8d598682f08574a',
            'prompt_sha256': 
'7e9e1c1ec8d9e6535abedb695bef6dccfc0d65906b77e308f8ab6b6669aeed42',
            'adapter_id': None,
            'adapter_sha': None,
            'max_new_tokens': None,
            'batch_size': 1,
            'dtype': None,
            'decoding': 'deterministic rules',
            'n': 50,
            'date': '2026-10-16T11:32:40.535460+00:00',
            'source': 
'C:/Users/vedan/AppData/Local/Temp/tiffintally-qa-9239ocaz/offline-eval/regex/t
est.jsonl'
        }
    },
    'model': 'NOT RUN (needs approval)',
    'cost': 'NOT MEASURED',
    'human_holdout': "NOT RUN: [Errno 2] No such file or directory: 
'data\\\\private\\\\real_test.jsonl'"
}
Saved per-row predictions and summary under 
C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\offline-eval

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

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/run_baselines.py --system regex --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\baseline-qa

```text
{
  "n": 50,
  "strict": {
    "hits": 35,
    "accuracy": 0.7,
    "wilson_95": [
      0.562496495355466,
      0.8089644649911906
    ]
  },
  "lenient": {
    "hits": 47,
    "accuracy": 0.94,
    "wilson_95": [
      0.8378290831116182,
      0.979385029651026
    ]
  },
  "chitchat": {
    "n": 2,
    "strict_hits": 2
  },
  "intent": {
    "n": 48,
    "strict_hits": 33
  },
  "metadata": {
    "dataset": "data\\synthetic\\test.jsonl",
    "dataset_sha256": "6e9f49ed006fc638210a64fc9a1246e6378fb87c68e10e0932e77a142e9509bd",
    "system": "regex",
    "prompt_sha256": "7e9e1c1ec8d9e6535abedb695bef6dccfc0d65906b77e308f8ab6b6669aeed42",
    "code_sha": "76acb4833e8b40b68a8fb977d8d598682f08574a",
    "n": 50,
    "adapter_id": null,
    "adapter_sha": null,
    "max_new_tokens": null,
    "batch_size": 1,
    "dtype": null,
    "decoding": "deterministic rules",
    "date": "2026-10-16T11:32:44.208289+00:00",
    "llm_rows": 0,
    "deferred": 0,
    "requested_batch_size": 20,
    "status": "measured"
  }
}

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/run_baselines.py --system hybrid --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\baseline-qa

```text
{
  "n": 50,
  "strict": {
    "hits": 35,
    "accuracy": 0.7,
    "wilson_95": [
      0.562496495355466,
      0.8089644649911906
    ]
  },
  "lenient": {
    "hits": 47,
    "accuracy": 0.94,
    "wilson_95": [
      0.8378290831116182,
      0.979385029651026
    ]
  },
  "chitchat": {
    "n": 2,
    "strict_hits": 2
  },
  "intent": {
    "n": 48,
    "strict_hits": 33
  },
  "metadata": {
    "dataset": "data\\synthetic\\test.jsonl",
    "dataset_sha256": "6e9f49ed006fc638210a64fc9a1246e6378fb87c68e10e0932e77a142e9509bd",
    "system": "hybrid_offline_rules_only",
    "prompt_sha256": "7e9e1c1ec8d9e6535abedb695bef6dccfc0d65906b77e308f8ab6b6669aeed42",
    "code_sha": "76acb4833e8b40b68a8fb977d8d598682f08574a",
    "n": 50,
    "adapter_id": null,
    "adapter_sha": null,
    "max_new_tokens": null,
    "batch_size": 1,
    "dtype": null,
    "decoding": "deterministic rules",
    "date": "2026-10-16T11:32:44.723550+00:00",
    "llm_rows": 0,
    "deferred": 5,
    "requested_batch_size": 20,
    "status": "INCOMPLETE: flagged rows deferred"
  }
}

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/run_baselines.py --system adapter --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-9239ocaz\baseline-qa

```text
{
  "system": "adapter",
  "status": "NOT RUN (needs approval or credentials)",
  "n": 0
}

```

Executed checks: PASS

This is a separate QA pass by the same agent, not an independent human review. Missing original probes and human acceptance items are not certified by these commands.
