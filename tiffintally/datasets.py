"""Dataset loading with mandatory human provenance for private held-out files."""

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
            if provenance["consent"] is not True:
                raise ValueError("Consent must be explicitly true")
            if provenance["source"] not in {"collected_from_cook", "written_by_vedant_blind"}:
                raise ValueError("Holdout must be collected or written blind by a human")
    return rows
