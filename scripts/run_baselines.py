"""Same-row baseline runner. Offline by default; approval precedes GPU requests."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from tiffintally.datasets import load_dataset
from tiffintally.extract.base import SYSTEM_PROMPT, heuristic_extract
from tiffintally.gpu_budget import GpuBudget
from tiffintally.model_validation import clean_model_event
from tiffintally.scoring import score_events, summarize


def few_shot_prompt():
    # Stable examples selected by training ID, never from dev or test performance.
    train = sorted(load_dataset(Path("data/synthetic/train.jsonl")), key=lambda row: row["id"])
    examples = [
        dict(text=row["raw_text"], sender=row["sender"], events=[row["gold"]]) for row in train[:8]
    ]
    return SYSTEM_PROMPT + "\nTraining examples:\n" + json.dumps(examples, ensure_ascii=False)


def run(system, dataset, out, *, execute=False, batch_size=20):
    source = Path(dataset)
    samples = load_dataset(source, private="private" in source.parts)
    if "private" in source.parts:
        raise PermissionError(
            "Human holdout consumption is not automatic; freeze and approve a separate once-per-system run first"
        )
    prompt = few_shot_prompt() if system == "few_shot_base" else SYSTEM_PROMPT
    status = "measured offline" if system == "regex" else "NOT RUN (needs approval or credentials)"
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if system not in {"regex", "hybrid"} and not execute:
        result = dict(system=system, status=status, n=0)
        (out / "status.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    budget = None
    if execute and system in {"adapter", "base", "few_shot_base", "hybrid"}:
        budget = GpuBudget()
        # The existing endpoint cannot accept a custom prompt. Never label its
        # ordinary response as a few-shot baseline.
        if system == "few_shot_base":
            raise PermissionError(
                "NOT RUN: deployed endpoint has no versioned custom-prompt contract"
            )
    rows = []
    llm_rows = 0
    deferred = 0
    for sample in samples:
        text = sample.get("raw_text") or sample["text"]
        started = time.perf_counter()
        parsed = [
            event.model_dump(mode="json") for event in heuristic_extract(text, sample["sender"])
        ]
        flagged = any(event["needs_review"] or event["audit_flags"] for event in parsed)
        needs_model = system not in {"regex", "hybrid"} or (system == "hybrid" and flagged)
        raw_output = parsed
        parse_ok = True
        if needs_model and not execute:
            deferred += 1
        if needs_model and execute:
            if system == "gemini":
                # Kept explicit: no automatic fallback can become a model score.
                key = os.getenv("GOOGLE_API_KEY")
                model = os.getenv("GEMMA_MODEL")
                if not key or not model:
                    raise PermissionError("NOT RUN: GOOGLE_API_KEY and GEMMA_MODEL required")
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": key},
                    timeout=60,
                    json={
                        "contents": [{"parts": [{"text": prompt + "\n" + text}]}],
                        "generationConfig": {
                            "temperature": 0,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                response.raise_for_status()
                raw_output = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                try:
                    parsed = [
                        clean_model_event(event) for event in json.loads(raw_output)["events"]
                    ]
                except (ValueError, KeyError, TypeError):
                    parsed, parse_ok = [], False
            else:
                url = os.getenv("MODAL_EXTRACTOR_URL")
                token = os.getenv("MODAL_EXTRACTOR_TOKEN")
                if not url or not token:
                    raise PermissionError("NOT RUN: Modal endpoint credentials missing")
                budget.reserve(1)  # Reservation is spent even on a failed request; no retries.
                response = httpx.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60,
                    json={
                        "use_adapter": system in {"adapter", "hybrid"},
                        "messages": [{"sender": sample["sender"], "text": text}],
                    },
                )
                response.raise_for_status()
                body = response.json()
                raw_output = body.get("raw", [None])[0]
                parsed = body.get("results", [[]])[0]
                parse_ok = isinstance(parsed, list) and bool(raw_output)
                if raw_output is None:
                    raise ValueError(
                        "Endpoint did not save raw generation; cannot publish a model measurement"
                    )
            llm_rows += 1
        gold = sample["gold"] if isinstance(sample["gold"], list) else [sample["gold"]]
        rows.append(
            dict(
                id=sample["id"],
                template_id=sample.get("template_id", sample["id"]),
                text=text,
                raw_output=raw_output,
                parsed=parsed,
                gold=gold,
                parse_ok=parse_ok,
                latency_ms=(time.perf_counter() - started) * 1000,
                **score_events(parsed, gold, parse_ok=parse_ok),
            )
        )
    (out / "test.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    metadata = dict(
        dataset=str(source),
        dataset_sha256=hashlib.sha256(source.read_text(encoding="utf-8").encode()).hexdigest(),
        system=system if execute or system == "regex" else "hybrid_offline_rules_only",
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        code_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        n=len(rows),
        adapter_id="iteration_31" if system in {"adapter", "hybrid"} and llm_rows else None,
        adapter_sha=None,
        max_new_tokens=None,
        batch_size=1,
        dtype=None,
        decoding="endpoint configured; unverified" if llm_rows else "deterministic rules",
        date=datetime.now(timezone.utc).isoformat(),
        llm_rows=llm_rows,
        deferred=deferred,
        requested_batch_size=batch_size,
        status="INCOMPLETE: flagged rows deferred" if deferred else "measured",
    )
    (out / "test.meta.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    result = dict(**summarize(rows), metadata=metadata)
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--system",
        choices=("regex", "hybrid", "base", "few_shot_base", "adapter", "gemini"),
        default="regex",
    )
    parser.add_argument("--dataset", type=Path, default=Path("data/synthetic/test.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("evals/final/baselines"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.system, args.dataset, args.out / args.system, execute=args.execute), indent=2
        )
    )


if __name__ == "__main__":
    main()
