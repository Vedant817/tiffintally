"""Dataset loading with mandatory human provenance for private held-out files."""

import hashlib
import json
from pathlib import Path

PROVENANCE_FIELDS = {
    "collector",
    "date",
    "consent",
    "source",
    "labeller",
    "label_date",
    "second_labeller",
}


def load_dataset(path: Path, *, private=False):
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError("Empty dataset")
    ids = set()
    for row in rows:
        if not row.get("id") or row["id"] in ids:
            raise ValueError("Dataset requires unique row IDs")
        ids.add(row["id"])
        if not row.get("gold") or not (row.get("raw_text") or row.get("text")):
            raise ValueError("Missing authored gold or text")
        if private:
            provenance = row.get("provenance")
            if not isinstance(provenance, dict) or not PROVENANCE_FIELDS <= provenance.keys():
                raise ValueError(
                    "Private holdout requires a complete provenance block on every row"
                )
            if not all(provenance[field] for field in PROVENANCE_FIELDS):
                raise ValueError("Empty provenance field")
            if any(
                isinstance(value, str)
                and value.strip().lower() in {"pending", "unknown", "not reviewed"}
                for value in provenance.values()
            ):
                raise ValueError("Unfinished provenance cannot qualify a held-out set")
            if provenance["consent"] is not True:
                raise ValueError("Consent must be explicitly true")
            if provenance["source"] not in {"collected_from_cook", "written_by_vedant_blind"}:
                raise ValueError("Holdout must be collected or written blind by a human")
    return rows


def reserve_holdout(path: Path, system: str, out: Path):
    """Consume a frozen private holdout once per named system, before inference."""
    if "private" not in out.parts:
        raise ValueError("Private per-row predictions must remain under data/private")
    report = json.loads((path.parent / "real_test.freeze.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
    if report.get(path.name, {}).get("sha256") != digest:
        raise ValueError("Held-out file does not match its pre-score freeze")
    if not system.replace("_", "").isalnum():
        raise ValueError("Invalid system identifier")
    receipts = path.parent / "holdout_consumed"
    receipts.mkdir(exist_ok=True)
    with (receipts / f"{system}.json").open("x", encoding="utf-8") as stream:
        json.dump(
            dict(
                system=system,
                sha256=digest,
                status="reserved before scoring; failures still consume the run",
            ),
            stream,
        )
