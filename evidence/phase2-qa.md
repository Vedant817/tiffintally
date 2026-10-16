# phase2: clean-clone QA

Clone: `C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-zzjkmsxw\repo`

Original auditor probe sources: NOT SUPPLIED. Reconstructed probes are identified in tests/probes/README.md.

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe check .

```text
All checks passed!

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\ruff.exe format --check .

```text
101 files already formatted

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest -q

```text
........................................................................ [ 31%]
........................................................................ [ 63%]
........................................................................ [ 95%]
..........                                                               [100%]
============================== warnings summary ===============================
tests\test_app.py:3
  C:\Users\vedan\AppData\Local\Temp\tiffintally-qa-zzjkmsxw\repo\tests\test_app.py:3: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
226 passed, 1 warning in 6.27s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe scripts/check_claims.py

```text
PASS: claim registration (historical entries remain unverified)

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=0

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 2.02s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=1

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 1.82s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=42

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 1.93s

```

## PASS: C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Scripts\python.exe -m pytest tests/test_daily_invariants.py -q --hypothesis-seed=271

```text
......                                                                   [100%]
============================== warnings summary ===============================
tests/test_daily_invariants.py::test_balance_csv_and_explicit_alias_confirmation
  C:\Users\vedan\Documents\Resources\Code\tiffin-tally\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 1 warning in 1.85s

```

Executed checks: PASS

This is a separate QA pass by the same agent, not an independent human review. Missing original probes and human acceptance items are not certified by these commands.
