"""Test-wide isolation.

Two rules from the self-review:

1. A test run must never mutate a tracked file. Model-call telemetry therefore goes
   to a tmp path, not `evals/telemetry.jsonl`.
2. A test run must never open a network connection to Sentry. `init_telemetry`
   returns early when TIFFINTALLY_TELEMETRY is off, so no "Sentry is attempting to
   send N pending events" line trails the pytest summary.

Set before any tiffintally import so module-level readers see it too.
"""

import os
import tempfile
from pathlib import Path

os.environ["TIFFINTALLY_TELEMETRY"] = "0"
os.environ.setdefault(
    "TELEMETRY_LOG",
    str(Path(tempfile.gettempdir()) / "tiffintally-test-telemetry.jsonl"),
)

# No live keys during tests: the extractor's "no key configured" path is the
# default so a developer's real .env cannot leak into a test run.
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("ELEVENLABS_API_KEY", None)
os.environ.pop("TINKER_API_KEY", None)
