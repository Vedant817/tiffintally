"""Index behavioral claims to implementation and executed test evidence."""

import json
import subprocess
from pathlib import Path

CLAIMS = [
    (
        "Primary identity comes from the source sender",
        "tiffintally/extract/gemma.py",
        "ev.customer = msg.sender",
        "tests/test_modal_integration.py",
    ),
    (
        "Payments need eligible session confirmation",
        "tiffintally/reconcile.py",
        "if not payment_is_safe(ev)",
        "tests/test_modal_integration.py",
    ),
    (
        "Duplicate source payments are credited once",
        "tiffintally/reconcile.py",
        "if identity in seen_payments",
        "tests/test_modal_integration.py",
    ),
    (
        "Token maps default to instance memory",
        "tiffintally/privacy.py",
        'self.db_path = Path(":memory:")',
        "tests/test_round4_privacy.py",
    ),
    (
        "Sheet and ledger share daily replay",
        "tiffintally/reconcile.py",
        "def _replay_day",
        "tests/test_daily_invariants.py",
    ),
    (
        "Session creation has a hard cap",
        "tiffintally/app.py",
        "while len(SESSIONS) >= MAX_SESSIONS",
        "tests/test_session_cap.py",
    ),
    (
        "Private holdouts require provenance and freezing",
        "tiffintally/datasets.py",
        "def reserve_holdout",
        "tests/test_human_holdout.py",
    ),
    (
        "Numerical tables rescore saved predictions",
        "scripts/publish_results.py",
        "rows = load(ROOT / source)",
        "evals/final/public_summary.json",
    ),
]


def main():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    rows = []
    for claim, file, needle, evidence in CLAIMS:
        lines = Path(file).read_text(encoding="utf-8").splitlines()
        line = next(i for i, text in enumerate(lines, 1) if needle in text)
        rows.append(
            dict(
                claim=claim,
                implementation=f"{file}:{line}",
                evidence=evidence,
                last_verified_sha=sha,
                verification="local tests; see evidence/final-qa.md",
            )
        )
    Path("evals/final/claims.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    output = [
        "# Current claims",
        "",
        "Generated from implementation and local evidence; not production certification.",
        "",
        "| Claim | Implementation | Source evidence | Last verified SHA |",
        "|---|---|---|---|",
    ]
    output += [f"| {r['claim']} | {r['implementation']} | {r['evidence']} | {sha} |" for r in rows]
    Path("docs/CLAIMS.md").write_text("\n".join(output) + "\n", encoding="utf-8")
    print("Wrote implementation claim index; hosted/device proof is not claimed.")


if __name__ == "__main__":
    main()
