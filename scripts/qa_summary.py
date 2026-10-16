"""Extract QA counts and the actual clean-clone revision from saved command output."""

import hashlib
import json
import re
import subprocess
from pathlib import Path


def main():
    path = Path("evidence/final-qa.md")
    text = path.read_text(encoding="utf-8")
    clone = re.search(r"Clone: `([^`]+)`", text).group(1)
    sha = subprocess.check_output(["git", "-C", clone, "rev-parse", "HEAD"], text=True).strip()
    passed, expected_failures = re.search(r"(\d+) passed, (\d+) xfailed", text).groups()
    if "Executed checks: PASS" not in text or "## FAIL:" in text:
        raise SystemExit("QA output contains a failed check")
    result = dict(
        source_code_sha=sha,
        tests_passed=int(passed),
        expected_failures=int(expected_failures),
        artifact="evidence/final-qa.md",
        artifact_sha256=hashlib.sha256(text.encode()).hexdigest(),
        environment="fresh clone and its own uv-installed environment",
        status="PASS",
        original_probes="NOT SUPPLIED",
        hosted_models="NOT RUN",
    )
    Path("evals/final/qa_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
