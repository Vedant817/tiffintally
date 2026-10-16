"""Paired event-set comparison from saved predictions, clustered by template."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from tiffintally.scoring import score_events, summarize


def load(path):
    rows = [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line
    ]
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Empty predictions or duplicate IDs")
    for row in rows:
        scores = score_events(row["parsed"], row["gold"], parse_ok=row.get("parse_ok", True))
        for key in ("strict_ok", "lenient_ok", "per_field_ok"):
            if row[key] != scores[key]:
                raise ValueError(f"Saved correctness disagrees with scorer: {row['id']} {key}")
    return rows


def compare(left, right, draws=20000, seed=271):
    a = {row["id"]: row for row in left}
    b = {row["id"]: row for row in right}
    if set(a) != set(b):
        raise ValueError("Paired inputs must contain exactly the same row IDs")
    groups = defaultdict(list)
    discordant = [0, 0]
    for key in sorted(a):
        if a[key]["gold"] != b[key]["gold"] or a[key]["text"] != b[key]["text"]:
            raise ValueError(f"Different row/gold content for {key}")
        if a[key].get("template_id") != b[key].get("template_id"):
            raise ValueError("Template assignments differ")
        delta = int(b[key]["strict_ok"]) - int(a[key]["strict_ok"])
        groups[a[key].get("template_id") or key].append(delta)
        if delta:
            discordant[delta > 0] += 1
    count = sum(discordant)
    p_value = (
        min(1.0, 2 * sum(math.comb(count, i) for i in range(min(discordant) + 1)) / 2**count)
        if count
        else 1.0
    )
    sums = np.array([sum(values) for values in groups.values()])
    sizes = np.array([len(values) for values in groups.values()])
    rng = np.random.default_rng(seed)
    samples = rng.integers(len(groups), size=(draws, len(groups)))
    deltas = sums[samples].sum(axis=1) / sizes[samples].sum(axis=1)
    interval = np.quantile(deltas, [0.025, 0.975]).tolist()
    return dict(
        n=len(a),
        templates=len(groups),
        discordant_left_only=discordant[0],
        discordant_right_only=discordant[1],
        exact_mcnemar_p=p_value,
        delta_right_minus_left=float(sums.sum() / sizes.sum()),
        template_clustered_95=interval,
        bootstrap_draws=draws,
        seed=seed,
        left=summarize(left),
        right=summarize(right),
        per_template={
            key: dict(n=len(values), delta=sum(values) / len(values))
            for key, values in groups.items()
        },
        leave_one_template_out={
            key: (sum(sums) - sum(values)) / (len(a) - len(values))
            if len(a) != len(values)
            else None
            for key, values in groups.items()
        },
        conclusion="No superiority claim is supported."
        if interval[0] <= 0 <= interval[1]
        else "A difference exists on these rows; this does not establish real-message accuracy.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = compare(load(args.left), load(args.right))
    output = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "n",
                    "templates",
                    "exact_mcnemar_p",
                    "template_clustered_95",
                    "conclusion",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
