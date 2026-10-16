"""Report sibling phrasing without repairing or filtering an already scored test."""

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from tiffintally.datasets import load_dataset


def signature(text, names):
    for name in sorted((name for name in names if name), key=len, reverse=True):
        if name:
            text = re.sub(rf"\b{re.escape(name)}\b", " PERSON ", text, flags=re.I)
    return " ".join(re.sub(r"\d+(?:[,.]\d+)*", " NUMBER ", text.lower()).split())


def grams(text):
    return {text[index : index + 4] for index in range(max(1, len(text) - 3))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("evals/final/leakage.json"))
    parser.add_argument(
        "--check-known",
        action="store_true",
        help="Succeed only if failures exactly match the saved report",
    )
    args = parser.parse_args()
    from tiffintally.extract.base import SYSTEM_PROMPT

    train = load_dataset(Path("data/synthetic/train.jsonl"))
    names = {r["sender"] for r in train} | {r["gold"].get("secondary_customer") for r in train}
    candidates = [(row, signature(row["raw_text"], names)) for row in train]
    output = []
    violations = []
    for split in ("test", "dev2"):
        for row in load_dataset(Path(f"data/synthetic/{split}.jsonl")):
            masked = signature(row["raw_text"], names | {row["sender"]})
            scored = []
            matching_neighbours = []
            for other, text in candidates:
                a, b = grams(masked), grams(text)
                jaccard = len(a & b) / len(a | b) if a | b else 1
                scored.append((jaccard, SequenceMatcher(None, masked, text).ratio(), other, text))
                if (
                    split == "test"
                    and jaccard >= 0.6
                    and all(
                        row["gold"].get(field) == other["gold"].get(field)
                        for field in ("meal", "qty", "action", "mods")
                    )
                ):
                    matching_neighbours.append([other["id"], jaccard])
            jaccard, ratio, nearest, sig = max(scored, key=lambda pair: (pair[0], pair[1]))
            label_fields = ("meal", "qty", "action", "mods")
            same_label = all(row["gold"].get(k) == nearest["gold"].get(k) for k in label_fields)
            prompt_copy = row["raw_text"].lower() in SYSTEM_PROMPT.lower()
            item = dict(
                split=split,
                id=row["id"],
                train_id=nearest["id"],
                jaccard=jaccard,
                edit_ratio=ratio,
                masked_signature=masked,
                nearest_signature=sig,
                signature_equal=masked == sig,
                same_label=same_label,
                sibling_template=jaccard >= 0.5,
                prompt_copy=prompt_copy,
            )
            output.append(item)
            item["same_label_neighbours_above_threshold"] = matching_neighbours
            if matching_neighbours or prompt_copy:
                violations.append(item)
    report = dict(
        rows=output,
        violations=violations,
        original_probe_baseline="AUDIT4 reports three test neighbours above 0.5; original probe source/output not supplied. Different normalization may differ.",
    )
    if args.check_known:
        known = json.loads(args.out.read_text(encoding="utf-8"))
        if report != known:
            raise SystemExit("FAIL: leakage report changed; review the changed pairs")
        print("Known leakage exactly reproduced; not a clean-split certification.")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Known split leakage",
        "",
        "Do not tune away these findings or rewrite the frozen test.",
        "",
        "This report uses masked character shingles, not the unavailable auditor script.",
        "",
        "| Split | Row | Train neighbour | Jaccard | Prompt copy |",
        "|---|---|---|---|---|",
    ]
    for item in violations:
        lines.append(
            f"| {item['split']} | {item['id']} | {item['train_id']} | {item['jaccard']:.3f} | {item['prompt_copy']} |"
        )
    lines += [
        "",
        "All neighbour distances and sibling pairs: `evals/final/leakage.json`. "
        "Legacy dev is a training subset. dev2 is agent-authored synthetic development, "
        "not an independent human evaluation. The split_report.json legacy note is wrong; "
        "its hashes are preserved, with corrected metadata in split_report_v2.json.",
    ]
    Path("docs/KNOWN_LEAKS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"{'FAIL' if violations else 'PASS'}: {len(violations)} leakage violations (saved and documented)"
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
