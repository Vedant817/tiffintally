# phase0: clean-clone QA

Clone: `C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-v6xsvu2a\repo`

Original auditor probe sources: NOT SUPPLIED. Reconstructed probes are identified in tests/probes/README.md.

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe check .

```text
All checks passed!

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe format --check .

```text
94 files already formatted

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest -q

```text
xx...................................................................... [ 35%]
........................................................................ [ 70%]
.............................................................            [100%]
============================== warnings summary ===============================
tests\test_app.py:3
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-v6xsvu2a\repo\tests\test_app.py:3: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
203 passed, 2 xfailed, 1 warning in 4.77s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/check_claims.py

```text
PASS: claim registration (historical entries remain unverified)

```

Executed checks: PASS

This is a separate QA pass by the same agent, not an independent human review. Missing original probes and human acceptance items are not certified by these commands.
