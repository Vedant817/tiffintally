# final: clean-clone QA

Clone: `C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo`

Original auditor probe sources: NOT SUPPLIED. Reconstructed probes are identified in tests/probes/README.md.

## PASS: uv sync --frozen --all-extras --dev --link-mode hardlink

```text
Using CPython 3.12.15
Creating virtual environment at: .venv
   Building tiffintally @ file:///C:/Users/vedan/AppData/Local/Temp/tiffintally-qa-js46a6_c/repo
Downloading numpy (12.0MiB)
Downloading modal (1.0MiB)
Downloading pydantic-core (2.0MiB)
 Downloaded modal
 Downloaded pydantic-core
      Built tiffintally @ file:///C:/Users/vedan/AppData/Local/Temp/tiffintally-qa-js46a6_c/repo
 Downloaded numpy
Prepared 32 packages in 8.51s
Installed 63 packages in 2.41s
 + aiohappyeyeballs==2.7.1
 + aiohttp==3.14.5
 + aiosignal==1.4.0
 + annotated-doc==0.0.5
 + annotated-types==0.8.0
 + anyio==4.15.1
 + attrs==26.1.0
 + cbor2==6.1.5
 + certifi==2026.7.22
 + click==8.5.0
 + colorama==0.4.6
 + fastapi==0.143.0
 + frozenlist==1.8.0
 + grpclib==0.4.9
 + h11==0.16.0
 + h2==4.4.1
 + hpack==4.2.0
 + httpcore==1.0.9
 + httptools==0.9.0
 + httpx==0.28.1
 + hyperframe==6.1.0
 + hypothesis==6.170.0
 + idna==3.20
 + iniconfig==2.3.1
 + jinja2==3.1.6
 + markdown-it-py==4.2.0
 + markupsafe==3.0.4
 + mdurl==0.1.2
 + modal==1.6.1
 + multidict==7.1.0
 + numpy==2.5.4
 + opentelemetry-api==1.45.1
 + packaging==26.3
 + pluggy==1.6.0
 + propcache==0.5.4
 + protobuf==7.36.2
 + pydantic==2.13.4
 + pydantic-core==2.46.4
 + pygments==2.21.0
 + pytest==9.1.1
 + pytest-asyncio==1.4.0
 + python-dotenv==1.2.4
 + python-multipart==0.0.32
 + pyyaml==6.0.3
 + rich==15.0.0
 + ruff==0.17.0
 + sentry-sdk==2.72.0
 + shellingham==1.5.4
 + sortedcontainers==2.4.0
 + starlette==1.8.0
 + synchronicity==0.12.6
 + tiffintally==0.1.0 (from file:///C:/Users/vedan/AppData/Local/Temp/tiffintally-qa-js46a6_c/repo)
 + toml==0.10.2
 + typer==0.27.3
 + types-certifi==2021.10.8.3
 + types-toml==0.10.8.20260518
 + typing-extensions==4.16.0
 + typing-inspection==0.4.4
 + urllib3==2.8.0
 + uvicorn==0.54.0
 + watchfiles==1.3.0
 + websockets==17.2
 + yarl==1.25.1

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\ruff.exe check .

```text
All checks passed!

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\ruff.exe format --check .

```text
127 files already formatted

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -m pytest -q

```text
........................................................................ [ 24%]
............................x.x.xx...................................... [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
.........                                                                [100%]
============================== warnings summary ===============================
tests\test_app.py:3
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\tests\test_app.py:3: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
293 passed, 4 xfailed, 1 warning in 26.45s

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/check_claims.py

```text
PASS: source-backed current claims; historical entries remain unverified

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=0

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 4.04s

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=1

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 3.90s

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=42

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 4.30s

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=271

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 3.93s

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -m tiffintally.cli eval --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\offline-eval

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
            'code_sha': '9532f00916e2fe4c956670a0997e6d57a86ac3df',
            'prompt_sha256': 
'7e9e1c1ec8d9e6535abedb695bef6dccfc0d65906b77e308f8ab6b6669aeed42',
            'adapter_id': None,
            'adapter_sha': None,
            'max_new_tokens': None,
            'batch_size': 1,
            'dtype': None,
            'decoding': 'deterministic rules',
            'n': 50,
            'date': '2026-10-16T11:34:43.538986+00:00',
            'source': 
'C:/Users/vedan/AppData/Local/Temp/tiffintally-qa-js46a6_c/offline-eval/regex/t
est.jsonl'
        }
    },
    'model': 'NOT RUN (needs approval)',
    'cost': 'NOT MEASURED',
    'human_holdout': "NOT RUN: [Errno 2] No such file or directory: 
'data\\\\private\\\\real_test.jsonl'"
}
Saved per-row predictions and summary under 
C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\offline-eval

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/leakage_report.py --check-known

```text
Known leakage exactly reproduced; not a clean-split certification.

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/compare.py evals/final/regex/test.jsonl evals/final/regex/test.jsonl

```text
{"n": 50, "templates": 36, "exact_mcnemar_p": 1.0, "template_clustered_95": [0.0, 0.0], "conclusion": "No superiority claim is supported."}

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/publish_results.py --check

```text
PASS: public tables match saved predictions

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/run_baselines.py --system regex --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\baseline-qa

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
    "code_sha": "9532f00916e2fe4c956670a0997e6d57a86ac3df",
    "n": 50,
    "adapter_id": null,
    "adapter_sha": null,
    "max_new_tokens": null,
    "batch_size": 1,
    "dtype": null,
    "decoding": "deterministic rules",
    "date": "2026-10-16T11:34:49.314312+00:00",
    "llm_rows": 0,
    "deferred": 0,
    "requested_batch_size": 20,
    "status": "measured"
  }
}

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/run_baselines.py --system hybrid --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\baseline-qa

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
    "code_sha": "9532f00916e2fe4c956670a0997e6d57a86ac3df",
    "n": 50,
    "adapter_id": null,
    "adapter_sha": null,
    "max_new_tokens": null,
    "batch_size": 1,
    "dtype": null,
    "decoding": "deterministic rules",
    "date": "2026-10-16T11:34:50.154268+00:00",
    "llm_rows": 0,
    "deferred": 5,
    "requested_batch_size": 20,
    "status": "INCOMPLETE: flagged rows deferred"
  }
}

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe scripts/run_baselines.py --system adapter --out C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\baseline-qa

```text
{
  "system": "adapter",
  "status": "NOT RUN (needs approval or credentials)",
  "n": 0
}

```

## PASS: C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\.venv\Scripts\python.exe -c import tiffintally; print(tiffintally.__file__)

```text
C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-js46a6_c\repo\tiffintally\__init__.py

```

## PASS: git diff --exit-code 4c24ec6 -- data/synthetic/test.jsonl data/synthetic/dev.jsonl data/synthetic/train.jsonl data/synthetic/split_report.json

```text

```

## PASS: gitleaks git . --redact --no-banner --log-opts=HEAD

```text
5:04PM INF Unknown SCM platform. Use --platform to include links in findings. host=
5:04PM INF 119 commits scanned.
5:04PM INF scanned ~19856703 bytes (19.86 MB) in 1.23s
5:04PM INF no leaks found

```

## PASS: git diff --exit-code

```text

```

Executed checks: PASS

This is a separate QA pass by the same agent, not an independent human review. Missing original probes and human acceptance items are not certified by these commands.
