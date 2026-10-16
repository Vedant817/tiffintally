"""Measure local rules latency; leave uncalled hosted configurations unmeasured."""

import json
import statistics
import time
from pathlib import Path

from tiffintally.datasets import load_dataset
from tiffintally.extract.base import heuristic_extract


def main():
    rows = load_dataset(Path("data/synthetic/dev2.jsonl"))
    results = []
    for batch_size in (1, 20, 40):
        for temperature in ("first_pass_not_process_cold", "warm"):
            durations = []
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                started = time.perf_counter()
                for row in batch:
                    heuristic_extract(row["raw_text"], row["sender"])
                elapsed = (time.perf_counter() - started) * 1000
                durations.extend([elapsed / len(batch)] * len(batch))
            results.append(
                dict(
                    system="regex",
                    batch_size=batch_size,
                    temperature=temperature,
                    n=len(durations),
                    p50_ms=statistics.median(durations),
                    p95_ms=sorted(durations)[int(0.95 * (len(durations) - 1))],
                    definition="batch wall time divided by messages, not individual request latency",
                )
            )
    report = dict(
        measurements=results,
        hosted="NOT RUN (needs approval)",
        cold_gpu="NOT MEASURED",
        cost_per_1k="NOT MEASURED (no billing record)",
    )
    Path("evals/final/latency.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("Saved local rules latency; hosted/cold-GPU latency and billing remain unmeasured.")


if __name__ == "__main__":
    main()
