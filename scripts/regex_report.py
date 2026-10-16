"""Freeze cleaned rules and save all predictions before publishing any aggregate."""

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from tiffintally.extract.base import SYSTEM_PROMPT, heuristic_extract
from tiffintally.scoring import score_events, summarize


def digest(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()


def run(split, out=Path("evals/final/regex")):
    output = []
    source = Path(f"data/synthetic/{split}.jsonl")
    for line in source.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        started = time.perf_counter()
        events = heuristic_extract(row["raw_text"], row["sender"])
        latency = (time.perf_counter() - started) * 1000
        parsed = [event.model_dump(mode="json") for event in events]
        gold = row["gold"] if isinstance(row["gold"], list) else [row["gold"]]
        output.append(
            dict(
                id=row["id"],
                template_id=row["template_id"],
                text=row["raw_text"],
                raw_output=parsed,
                parsed=parsed,
                gold=gold,
                latency_ms=latency,
                **score_events(parsed, gold),
            )
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{split}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8"
    )
    meta = dict(
        system="regex",
        code_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        prompt_sha256=hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        dataset_sha256=digest(source),
        adapter_id=None,
        adapter_sha=None,
        max_new_tokens=None,
        batch_size=1,
        dtype=None,
        decoding="deterministic rules",
        n=len(output),
        date=datetime.now(timezone.utc).isoformat(),
    )
    (out / f"{split}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return dict(
        **meta,
        **{k: v for k, v in summarize(output).items() if k != "n"},
        source=(out / f"{split}.jsonl").as_posix(),
    )


def main():
    destination = Path("evals/final/regex.json")
    if destination.exists():
        raise SystemExit("Refusing to overwrite frozen report; rescore saved predictions instead")
    frozen = {
        name: digest(name)
        for name in (
            "tiffintally/extract/base.py",
            "tiffintally/dates.py",
            "data/vocab/mod_patterns.json",
            "data/vocab/mods.json",
        )
    }
    Path("data/synthetic/rules_frozen_v2.json").write_text(
        json.dumps(frozen, indent=2) + "\n", encoding="utf-8"
    )
    reports = {split: run(split) for split in ("train", "dev2", "test")}
    destination.write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    for split, report in reports.items():
        print(split, json.dumps({key: report[key] for key in ("n", "strict", "lenient")}))


if __name__ == "__main__":
    main()
