"""The audit table, scored as OK / SAFE / WRONG.

OK: the preferred reading, including a review when review is what the row requires.
SAFE: routed to review (or no order) where a silent wrong answer was the old failure.
WRONG: a silent plausible order.

The reviewer's older 47-message set (OK22/SAFE6/WRONG19) is not in the repo and
cannot be re-run. This file is the table in FIX_PROMPT6B.
"""

from tiffintally.extract.base import heuristic_extract

# (message, group). group "diet" or "negation" must not be silently wrong.
ROWS = [
    ("no lunch tomorrow", "negation"),
    ("don't send lunch tomorrow", "negation"),
    ("kal ek thali kam", "negation"),
    ("kal lunch 1, aur ek extra roti", "diet"),
    ("kal lunch 2 nahi, 3 chahiye", "other"),
    ("kal lunch 2 ki jagah 3 kar do", "other"),
    ("kal lunch 1 thali, Priya ke liye bhi ek", "other"),
    ("kal shaam ko 1 thali", "other"),
    ("kal lunch? kitne baje aayega", "other"),
    ("Roommate left, cancel one thali from tomorrow", "negation"),
    ("Aaj raat 1 thali, bina pyaaz lahsun.", "diet"),
    ("kal lunch 1, kam mirchi", "diet"),
    ("kal lunch 1 less oil please", "diet"),
    ("bina pyaz kal lunch 1", "diet"),
    ("pyaz nahi daalna kal lunch 1", "diet"),
    ("kal lunch 1 extra chapati", "diet"),
    ("kal lunch 1 peanut allergy please careful", "diet"),
    ("kal lunch 1, no sugar in anything, diabetic", "diet"),
    ("kal dono time ek ek", "other"),
    ("kal dono time 2 2", "other"),
    ("Monday to Friday lunch 1", "other"),
    ("kal se ek hafte tak lunch 1 daily", "other"),
    ("kal lunch 100", "other"),
    ("kal lunch 0", "other"),
]


def _reviewed(events) -> bool:
    return any(event.needs_review or event.audit_flags for event in events)


def _has(events, meal, qty, action) -> bool:
    return any(
        event.meal == meal and event.qty == qty and event.action == action for event in events
    )


def _mods(events, *names) -> bool:
    return any(all(name in event.mods for name in names) for event in events)


def _preferred(text, events) -> bool:
    if text in {"no lunch tomorrow", "don't send lunch tomorrow"}:
        return _has(events, "lunch", 0, "cancel")
    if text == "kal ek thali kam":
        return False  # a real decrement is not implemented; review is SAFE
    if text == "kal lunch 1, aur ek extra roti":
        return (
            _has(events, "lunch", 1, "new")
            and _mods(events, "extra roti")
            and not _reviewed(events)
        )
    if text in {"kal lunch 2 nahi, 3 chahiye", "kal lunch 2 ki jagah 3 kar do"}:
        return (
            _has(events, "lunch", 3, "new") or _has(events, "lunch", 3, "change")
        ) and not _reviewed(events)
    if text == "kal lunch 1 thali, Priya ke liye bhi ek":
        return any(
            event.meal == "lunch" and event.qty == 2 and event.secondary_customer == "Priya"
            for event in events
        ) and not _reviewed(events)
    if text == "kal shaam ko 1 thali":
        return _has(events, "dinner", 1, "new") and not _reviewed(events)
    if text == "kal lunch? kitne baje aayega":
        return not events or all(event.action in {"none", "pause"} for event in events)
    if text == "Roommate left, cancel one thali from tomorrow":
        return False
    if text == "Aaj raat 1 thali, bina pyaaz lahsun.":
        return _has(events, "dinner", 1, "new") and _mods(events, "no onion", "no garlic")
    if text == "kal lunch 1, kam mirchi":
        return _mods(events, "less spicy") and not _reviewed(events)
    if text == "kal lunch 1 less oil please":
        return _mods(events, "less oily") and not _reviewed(events)
    if text in {"bina pyaz kal lunch 1", "pyaz nahi daalna kal lunch 1"}:
        return _mods(events, "no onion") and not _reviewed(events)
    if text == "kal lunch 1 extra chapati":
        return _mods(events, "extra roti") and not _reviewed(events)
    if text in {
        "kal lunch 1 peanut allergy please careful",
        "kal lunch 1, no sugar in anything, diabetic",
    }:
        return _reviewed(events) and any(
            event.note and "unrecognised_request" in event.audit_flags for event in events
        )
    if text == "kal dono time ek ek":
        return _has(events, "both", 1, "new")
    if text == "kal dono time 2 2":
        return _has(events, "both", 2, "new")
    if text in {
        "Monday to Friday lunch 1",
        "kal se ek hafte tak lunch 1 daily",
        "kal lunch 100",
        "kal lunch 0",
    }:
        return _reviewed(events) and not any(
            event.action == "new" and not event.needs_review for event in events
        )
    return False


def _silent_wrong(text, events) -> bool:
    if _reviewed(events):
        return False
    if text in {"no lunch tomorrow", "don't send lunch tomorrow"}:
        return not _has(events, "lunch", 0, "cancel")
    if text in {"kal ek thali kam", "Roommate left, cancel one thali from tomorrow"}:
        return any(event.action == "new" for event in events) or any(
            event.action == "cancel" and event.meal == "lunch" for event in events
        )
    if text == "kal lunch? kitne baje aayega":
        return any(event.action == "new" for event in events)
    if text in {"Monday to Friday lunch 1", "kal se ek hafte tak lunch 1 daily"}:
        return any(event.action == "new" for event in events)
    if text in {"kal lunch 100", "kal lunch 0"}:
        return True
    if text.startswith("kal lunch 1 peanut") or "diabetic" in text:
        return True
    return not _preferred(text, events)


def classify(text: str) -> str:
    events = heuristic_extract(text, "Ravi")
    if _preferred(text, events):
        return "OK"
    if _reviewed(events) or (
        text == "kal lunch? kitne baje aayega"
        and not any(event.action == "new" and not event.needs_review for event in events)
    ):
        return "SAFE"
    if _silent_wrong(text, events):
        return "WRONG"
    return "WRONG"


def test_audit5_smoke_table(capsys):
    counts = {"OK": 0, "SAFE": 0, "WRONG": 0}
    diet_wrong = []
    for text, group in ROWS:
        verdict = classify(text)
        counts[verdict] += 1
        if verdict == "WRONG" and group in {"diet", "negation"}:
            diet_wrong.append(text)
        print(f"{verdict} {text}")
    print(f"OK{counts['OK']}/SAFE{counts['SAFE']}/WRONG{counts['WRONG']}")
    assert counts["WRONG"] <= 3
    assert diet_wrong == []
