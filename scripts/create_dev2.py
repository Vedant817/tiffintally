"""Create a new agent-written synthetic development set, never real evaluation data.

Labels below are authored explicitly; no product date resolver or extractor is used.
This is a tuning set, not an independent human holdout.
"""

import hashlib
import json
from pathlib import Path

TEMPLATES = [
    ("Booking for tomorrow: lunch {q} packs, please acknowledge.", "lunch", "new", []),
    ("Tomorrow's dinner requirement is {q} boxes; leave at reception.", "dinner", "new", []),
    ("Please keep tomorrow lunch {q}; no onion in mine.", "lunch", "new", ["no onion"]),
    ("My list for tomorrow reads dinner {q}, less spicy please.", "dinner", "new", ["less spicy"]),
    ("Confirming tomorrow lunch {q}. That is the final headcount.", "lunch", "new", []),
    ("For tomorrow's evening: dinner {q}, no curd on the side.", "dinner", "new", ["no curd"]),
    ("Aunty, tomorrow lunch {q} boxes; label the bag for me.", "lunch", "new", []),
    ("Tomorrow dinner {q} for the table by the window.", "dinner", "new", []),
    ("Tomorrow lunch {q}, bina pyaaz; please note the allergy.", "lunch", "new", ["no onion"]),
    ("Writing it down now: tomorrow dinner {q} with extra roti.", "dinner", "new", ["extra roti"]),
    ("For tomorrow lunch {q}, roti nahi rice in my pack.", "lunch", "new", ["roti nahi rice"]),
    ("Carry tomorrow dinner {q} separately from today's delivery.", "dinner", "new", []),
    ("Tomorrow lunch {q}, kam teekha so everyone can eat it.", "lunch", "new", ["less spicy"]),
    ("Reserving tomorrow dinner {q}; call when you get downstairs.", "dinner", "new", []),
    ("Tomorrow lunch {q} without changing the other day's booking.", "lunch", "new", []),
    ("Cancel my tomorrow lunch; plans changed for group {q}.", "lunch", "cancel", []),
    ("Tomorrow dinner cancel for booking number {q}.", "dinner", "cancel", []),
    ("Sunday off for our room {q}; kitchen need not deliver.", "both", "pause", []),
    ("Revised plan: change tomorrow lunch to {q} packs.", "lunch", "change", []),
    ("Correction for tomorrow: change dinner to {q} boxes.", "dinner", "change", []),
]


def main():
    path = Path("data/synthetic/dev2.jsonl")
    if path.exists():
        raise SystemExit("Refusing to overwrite dev2; use a versioned errata file")
    rows = []
    train = [
        json.loads(line)
        for line in Path("data/synthetic/train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    train_texts = {row["raw_text"].lower() for row in train}
    for index, (template, meal, action, mods) in enumerate(TEMPLATES):
        for qty in (1, 2, 3):
            text = template.format(q=qty)
            assert text.lower() not in train_texts
            rows.append(
                dict(
                    id=f"dev2_{index:02}_{qty}",
                    sender="Dev Writer",
                    raw_text=text,
                    template_id=f"dev2_{index:02}",
                    provenance="agent_written_synthetic_development",
                    gold=dict(
                        customer="Dev Writer",
                        date="sunday" if action == "pause" else "tomorrow",
                        meal=meal,
                        qty=0 if action in {"cancel", "pause"} else qty,
                        action=action,
                        mods=mods,
                        payment_amount=None,
                        secondary_customer=None,
                    ),
                )
            )
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    report = dict(
        dev_in_train=True,
        dev2_rows=len(rows),
        dev2_templates=len(TEMPLATES),
        dev2_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rule="Agent-authored synthetic tuning only; not a real or blind holdout. Frozen legacy files untouched.",
    )
    Path("data/synthetic/split_report_v2.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("Created synthetic dev2 and sidecar freeze report; no legacy split edited.")


if __name__ == "__main__":
    main()
