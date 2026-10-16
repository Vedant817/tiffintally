"""
Head-to-head: the on-device regex against the hosted open model.

This is the measurement the post's "why open matters" section rests on, so it is
run as a script rather than folded into `tiffintally eval`, which would bury it
in a fallback row.

What is measured, on the frozen split only:
  - per-field agreement (meal, qty, action, mods)
  - exact match
  - where each one wins, with the actual messages

Writes evals/runs/<ts>/head_to_head.json and prints a table. RESULTS.md is not
touched.

Usage:
    MODAL_EXTRACTOR_URL=https://<app>--tiffintally-extract-api.us-east.modal.run \\
        uv run python scripts/head_to_head.py
"""

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tiffintally.extract.base import heuristic_extract  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
FIELDS = ("meal", "qty", "action", "mods")


def load(path: Path) -> list:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def gold_of(row: dict) -> dict:
    gold = row.get("gold") or {}
    return {
        "meal": gold.get("meal", "unspecified"),
        "qty": int(gold.get("qty", 0) or 0),
        "action": gold.get("action", "none"),
        "mods": tuple(gold.get("mods") or []),
    }


def regex_predict(text: str, sender: str) -> dict:
    events = heuristic_extract(text, sender)
    ev = events[0] if events else None
    if ev is None:
        return {"meal": "unspecified", "qty": 0, "action": "none", "mods": ()}
    return {
        "meal": ev.meal,
        "qty": ev.qty,
        "action": ev.action,
        "mods": tuple(ev.mods),
    }


def model_predict(rows: list, url: str, batch_size: int = 20, use_adapter: bool = True) -> tuple:
    """Call the served endpoint and return predictions aligned with `rows`."""
    import httpx

    predictions = [None] * len(rows)
    metadata = {
        "model": "unknown",
        "gpu": "",
        "system_prompt_chars": 0,
        "repaired_blocks": 0,
        "empty_results": 0,
        "latencies": [],
    }

    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        payload = {
            "use_adapter": use_adapter,
            "messages": [
                {
                    "sender": r.get("sender", "Customer"),
                    "text": r.get("raw_text") or r.get("text", ""),
                }
                for r in chunk
            ],
        }
        began = time.perf_counter()
        response = httpx.post(url, json=payload, timeout=900.0)
        response.raise_for_status()
        body = response.json()

        metadata["model"] = body.get("model", metadata["model"])
        metadata["gpu"] = body.get("gpu", metadata["gpu"])
        metadata["system_prompt_chars"] = body.get("system_prompt_chars", 0)
        metadata["repaired_blocks"] += body.get("repaired_blocks", 0)
        metadata["empty_results"] += body.get("empty_results", 0)
        metadata["latencies"].append(round((time.perf_counter() - began) * 1000, 1))

        for offset, events in enumerate(body.get("results", [])):
            index = start + offset
            if index >= len(rows):
                break
            if not events:
                predictions[index] = {"meal": "unspecified", "qty": 0, "action": "none", "mods": ()}
                continue
            first = events[0]
            predictions[index] = {
                "meal": first.get("meal", "unspecified"),
                "qty": int(first.get("qty", 0) or 0),
                "action": first.get("action", "none"),
                "mods": tuple(first.get("mods") or []),
            }

    return predictions, metadata


def score(predictions: list, golds: list) -> dict:
    n = len(golds)
    if not n:
        return {"n": 0}
    per_field = {}
    for field in FIELDS:
        hits = sum(1 for p, g in zip(predictions, golds) if p and p[field] == g[field])
        per_field[field] = round(hits / n, 4)
    exact = sum(1 for p, g in zip(predictions, golds) if p and all(p[f] == g[f] for f in FIELDS))
    return {"n": n, "per_field": per_field, "exact_match": round(exact / n, 4)}


def main() -> int:
    url = os.getenv(
        "MODAL_EXTRACTOR_URL",
        "https://vedantmahajan271--tiffintally-extract-api.us-east.modal.run",
    )
    dataset = Path(os.getenv("H2H_DATASET", "data/synthetic/test.jsonl"))
    rows = load(dataset)
    if not rows:
        print(f"no rows in {dataset}")
        return 1

    golds = [gold_of(r) for r in rows]
    texts = [(r.get("raw_text") or r.get("text", "")) for r in rows]
    senders = [r.get("sender", "Customer") for r in rows]

    print(f"dataset: {dataset} ({len(rows)} rows)")
    print(f"model:   {url}\n")

    regex_preds = [regex_predict(t, s) for t, s in zip(texts, senders)]
    print("regex done, calling the served model...")
    model_preds, metadata = model_predict(rows, url)

    regex_score = score(regex_preds, golds)
    model_score = score(model_preds, golds)

    disagreements = []
    for row, text, gold, r_pred, m_pred in zip(rows, texts, golds, regex_preds, model_preds):
        r_ok = all(r_pred[f] == gold[f] for f in FIELDS)
        m_ok = all(m_pred[f] == gold[f] for f in FIELDS)
        if r_ok == m_ok:
            continue
        disagreements.append(
            {
                "text": text,
                "gold": {**gold, "mods": list(gold["mods"])},
                "regex": {**r_pred, "mods": list(r_pred["mods"])},
                "model": {**m_pred, "mods": list(m_pred["mods"])},
                "winner": "model" if m_ok else "regex",
            }
        )

    winners = Counter(d["winner"] for d in disagreements)

    stamp = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "evals" / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_timestamp": stamp,
        "date_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M %S IST"),
        "dataset": str(dataset).replace("\\", "/"),
        "dataset_rows": len(rows),
        "model_endpoint": url,
        "model": metadata["model"],
        "gpu": metadata["gpu"],
        "model_calls_ms": metadata["latencies"],
        "model_repaired_blocks": metadata["repaired_blocks"],
        "model_empty_results": metadata["empty_results"],
        "regex": regex_score,
        "open_model": model_score,
        "delta_exact_match": round(
            model_score.get("exact_match", 0) - regex_score.get("exact_match", 0), 4
        ),
        "disagreements": disagreements,
        "winner_counts": dict(winners),
    }
    (run_dir / "head_to_head.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    base_preds = None
    base_score = None
    base_metadata = None
    if os.getenv("H2H_CONTROL", "1") not in {"0", "false", "no"}:
        print("control: same prompt, same parser, no adapter...")
        base_preds, base_metadata = model_predict(rows, url, use_adapter=False)
        base_score = score(base_preds, golds)

    payload["base_model_no_adapter"] = base_score
    payload["base_model_endpoint"] = base_metadata["model"] if base_metadata else None
    payload["base_model_latencies_ms"] = base_metadata["latencies"] if base_metadata else []

    (run_dir / "head_to_head.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    columns = [
        ("Regex (on device)", regex_score),
        ("Qwen2.5-3B + LoRA", model_score),
    ]
    if base_score:
        columns.insert(1, ("Qwen2.5-3B raw", base_score))

    width = max(len(name) for name, _ in columns) + 2
    header = f"{'Metric':<18}" + "".join(f"{name:>{width + 4}}" for name, _ in columns)
    print("\n" + header)
    print("-" * len(header))
    print(
        f"{'Exact match':<18}"
        + "".join(f"{s['exact_match'] * 100:>{width + 3}.1f}%" for _, s in columns)
    )
    for field in FIELDS:
        print(
            f"{field:<18}" + "".join(f"{s['per_field'][field]:>{width + 4}.3f}" for _, s in columns)
        )

    print(
        f"\nserved model : {metadata['model']} on {metadata['gpu']}\n"
        f"prompt       : {metadata['system_prompt_chars']} chars from the image "
        "(the one the adapter was trained on)\n"
        f"repaired     : {metadata['repaired_blocks']} malformed JSON blocks fixed\n"
        f"empty results: {metadata['empty_results']} of {len(rows)} messages produced no event"
    )
    print(
        f"disagreements: {len(disagreements)} ({winners['model']} model, {winners['regex']} regex)"
    )
    print(f"saved         : evals/runs/{stamp}/head_to_head.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
