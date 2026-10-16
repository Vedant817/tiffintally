"""Event-set exact match. Unknown dietary constraints never count as equivalent."""

import json
import math
from pathlib import Path

STRICT_FIELDS = ("meal", "qty", "action", "mods", "payment_amount", "secondary_customer")
LENIENT_FIELDS = ("meal", "qty", "action")
VOCAB_PATH = Path(__file__).resolve().parents[1] / "data/vocab/mods.json"


def canonical_mods(mods):
    vocabulary = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    lookup = {
        alias.lower(): canonical for canonical, aliases in vocabulary.items() for alias in aliases
    }
    result = []
    for mod in mods or []:
        normal = lookup.get(str(mod).strip().lower())
        if normal is None:
            return None
        result.append(normal)
    return tuple(sorted(set(result)))


def normalize(event):
    row = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
    mods = canonical_mods(row.get("mods", []))
    return {
        "meal": row.get("meal"),
        "qty": row.get("qty"),
        "action": row.get("action"),
        "mods": mods,
        "payment_amount": row.get("payment_amount"),
        "secondary_customer": (row.get("secondary_customer") or "").strip().lower() or None,
    }


def _set(events, fields):
    return {tuple(event[field] for field in fields) for event in events}


def score_events(predicted, gold, *, parse_ok=True):
    if isinstance(gold, dict):
        gold = [gold]
    if isinstance(predicted, dict):
        predicted = [predicted]
    raw = [
        event.model_dump(mode="json") if hasattr(event, "model_dump") else event
        for event in predicted
    ]
    parse_ok &= not any(
        event.get("invalid")
        or any(
            flag.startswith(("model_invalid", "model_server", "malformed_model", "empty_model"))
            for flag in event.get("audit_flags", [])
        )
        for event in raw
    )
    expected = [normalize(event) for event in gold]
    actual = [normalize(event) for event in raw]
    # A valid empty event list represents no intent, but malformed text does not.
    if not actual and expected and all(event["action"] == "none" for event in expected):
        actual = expected
    per_field = {
        field: bool(parse_ok and _set(actual, (field,)) == _set(expected, (field,)))
        for field in STRICT_FIELDS
    }
    known_mods = all(event["mods"] is not None for event in actual + expected)
    strict = (
        parse_ok and known_mods and _set(actual, STRICT_FIELDS) == _set(expected, STRICT_FIELDS)
    )
    lenient = parse_ok and _set(actual, LENIENT_FIELDS) == _set(expected, LENIENT_FIELDS)
    return dict(per_field_ok=per_field, strict_ok=bool(strict), lenient_ok=bool(lenient))


def wilson(hits, n):
    if n == 0:
        return None
    z = 1.959963984540054
    p = hits / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def summarize(rows):
    result = {"n": len(rows)}
    for metric in ("strict", "lenient"):
        hits = sum(row[f"{metric}_ok"] for row in rows)
        result[metric] = dict(
            hits=hits,
            accuracy=hits / len(rows) if rows else None,
            wilson_95=wilson(hits, len(rows)),
        )
    for category, selected in (
        ("chitchat", [r for r in rows if all(e["action"] == "none" for e in r["gold"])]),
        ("intent", [r for r in rows if any(e["action"] != "none" for e in r["gold"])]),
    ):
        result[category] = {
            "n": len(selected),
            "strict_hits": sum(r["strict_ok"] for r in selected),
        }
    return result
