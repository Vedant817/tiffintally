"""Reject unregistered numerical claims; historical claims are explicitly unverified."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"\b\d+(?:\.\d+)?%|\bn\s*=\s*\d+", re.I)


def claims():
    paths = [ROOT / p for p in ("README.md", "RESULTS.md", "post.md", "evals/dashboard.html")]
    paths += list((ROOT / "docs").glob("*.md"))
    for path in paths:
        if path.name == "NUMBERS.md" or not path.exists():
            continue
        for line, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in PATTERN.finditer(text):
                yield {
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": line,
                    "number": match.group(),
                    "context": text.strip(),
                }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-legacy", action="store_true")
    args = parser.parse_args()
    registry = ROOT / "evals/final/legacy_claims.json"
    if args.inventory_legacy:
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "status": "UNVERIFIED HISTORICAL CLAIMS; not measurements",
                    "claims": list(claims()),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        rows = [
            "# Numerical claims registry",
            "",
            "Legacy entries inventory existing text; registration is not validation. "
            "Current measurements must come from saved per-row predictions.",
            "",
            "| Number | File:key | Script | SHA | Date | Status |",
            "|---|---|---|---|---|---|",
        ]
        for i, claim in enumerate(claims()):
            rows.append(
                f"| {claim['number']} | evals/final/legacy_claims.json:claims[{i}] | "
                "scripts/check_claims.py --inventory-legacy | 4c24ec6 | historical | unverified |"
            )
        rows += [
            "",
            "Historical run source: `evals/modal_run_iter_31.json`; its exact match "
            "includes date. The saved failures do not contain every prediction, so the aggregate "
            "cannot be independently rescored. This registry does not endorse it.",
        ]
        (ROOT / "docs/NUMBERS.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        return 0
    if not registry.exists():
        print("FAIL: numerical claims registry missing")
        return 1
    registered = {
        (c["file"], c["number"], c["context"]) for c in json.loads(registry.read_text())["claims"]
    }
    missing = [c for c in claims() if (c["file"], c["number"], c["context"]) not in registered]
    for claim in missing:
        print(f"UNREGISTERED {claim['file']}:{claim['line']}: {claim['number']}")
    print(
        f"{'FAIL' if missing else 'PASS'}: claim registration (historical entries remain unverified)"
    )
    return bool(missing)


if __name__ == "__main__":
    raise SystemExit(main())
