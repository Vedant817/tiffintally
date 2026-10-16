"""Validation shared by the serving parser and model clients.

Invalid rows retain their supplied fields for diagnosis, but cannot become orders.
No model-supplied identity, review decision or confirmation is authoritative.
"""

import math

VALID_ACTIONS = {"new", "change", "add", "cancel", "pause", "payment", "none"}
VALID_MEALS = {"lunch", "dinner", "both", "unspecified"}
FIELDS = {
    "customer",
    "secondary_customer",
    "secondary_qty",
    "date",
    "meal",
    "qty",
    "items",
    "mods",
    "action",
    "payment_amount",
    "payment_note",
    "confidence",
    "pause_until",
}


def clean_model_event(event: dict) -> dict:
    row = {key: value for key, value in event.items() if key in FIELDS}
    errors = []
    for field, allowed in (("meal", VALID_MEALS), ("action", VALID_ACTIONS)):
        if not isinstance(row.get(field), str) or row[field] not in allowed:
            errors.append(f"invalid_{field}")
    for field in ("qty", "secondary_qty"):
        if field not in row and field == "secondary_qty":
            continue
        value = row.get(field)
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if type(value) is not int or value < 0:
            errors.append(f"invalid_{field}")
        else:
            row[field] = value
    for field in ("items", "mods"):
        if field not in row:
            continue
        if not isinstance(row[field], list) or not all(isinstance(v, str) for v in row[field]):
            errors.append(f"invalid_{field}")
    for field in ("customer", "secondary_customer", "date", "payment_note", "pause_until"):
        if field in row and row[field] is not None and not isinstance(row[field], str):
            errors.append(f"invalid_{field}")
    for field in ("payment_amount", "confidence"):
        value = row.get(field)
        if value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            errors.append(f"invalid_{field}")
        elif field == "confidence" and value > 1:
            errors.append("invalid_confidence")
    if event.get("invalid"):
        errors.extend(event.get("invalid_reasons") or ["server_invalid"])
    if errors:
        row["invalid"] = True
        row["invalid_reasons"] = sorted(set(errors))
    return row
