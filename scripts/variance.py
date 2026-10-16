"""Offline order/batch sensitivity; never substitutes for GPU variance."""

import json
import random
from pathlib import Path

from tiffintally.datasets import load_dataset
from tiffintally.extract.base import heuristic_extract


def main():
    rows = load_dataset(Path("data/synthetic/test.jsonl"))
    runs = []
    reference = {}
    for seed, batch_size in enumerate((1, 2, 7, 20, 40)):
        order = rows[:]
        random.Random(seed).shuffle(order)
        predictions = {}
        for start in range(0, len(order), batch_size):
            for row in order[start : start + batch_size]:
                predictions[row["id"]] = [
                    event.model_dump(mode="json")
                    for event in heuristic_extract(row["raw_text"], row["sender"])
                ]
        if not reference:
            reference = predictions
        runs.append(
            dict(
                seed=seed,
                batch_size=batch_size,
                n=len(predictions),
                flips=[key for key, value in predictions.items() if value != reference[key]],
            )
        )
    report = dict(
        system="regex",
        runs=runs,
        gpu="NOT RUN (needs approval)",
        historical_adapter_variance="NOT REPRODUCIBLE: no complete saved predictions; neither verified nor disproved.",
    )
    Path("evals/final/variance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
