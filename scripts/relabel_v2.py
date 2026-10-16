"""Propose secondary-allocation errata for training rows without editing originals."""

import json
import re
from pathlib import Path


def main():
    output = []
    for line in Path("data/synthetic/train.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        gold = dict(row["gold"])
        if not gold.get("secondary_customer"):
            continue
        text = row["raw_text"].lower()
        proposed = [dict(gold, secondary_qty=1)]
        if "cancel" in text and "mera regular" in text:
            proposed = [
                dict(gold, action="cancel", qty=0, secondary_qty=0),
                dict(gold, action="new", qty=1, secondary_customer=None, secondary_qty=1),
            ]
        elif gold.get("qty") == 1 and re.search(r"\b(?:aur|bhi)\b", text):
            proposed[0]["qty"] = 2
        output.append(
            dict(
                id=row["id"],
                raw_text=row["raw_text"],
                original_gold=gold,
                proposed_gold=proposed,
                status="PROPOSED: human label review required",
                reason="qty is total; secondary_qty is a share, not additional plates",
            )
        )
    Path("data/synthetic/relabel_v2.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8"
    )
    print("Wrote proposed training errata; not used as evaluation gold.")


if __name__ == "__main__":
    main()
