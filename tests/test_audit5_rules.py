"""Reviewer messages from AUDIT5. Written before the extractor change.

A row passes when the rules either produce the reading a cook would use, or
send the message to review. A silent plausible order is a failure.
"""

import pytest

from tiffintally.extract.base import heuristic_extract
from tiffintally.reconcile import _apply_event
from tiffintally.schema import OrderEvent


def _events(text: str):
    return heuristic_extract(text, "Ravi")


def _reviewed(events) -> bool:
    return any(event.needs_review or event.audit_flags for event in events)


def _order(events, meal: str, qty: int, action: str):
    return any(
        event.meal == meal and event.qty == qty and event.action == action for event in events
    )


@pytest.mark.parametrize(
    "text",
    ["no lunch tomorrow", "don't send lunch tomorrow"],
)
def test_english_negation_cancels_lunch(text):
    events = _events(text)
    assert _order(events, "lunch", 0, "cancel")
    assert not any(event.action == "new" and event.meal == "lunch" for event in events)


def test_one_fewer_is_not_a_new_plate():
    events = _events("kal ek thali kam")
    assert not any(event.action == "new" for event in events)
    assert _reviewed(events) or any(event.action in {"change", "add"} for event in events)


def test_extra_roti_does_not_add_a_plate():
    events = _events("kal lunch 1, aur ek extra roti")
    assert _order(events, "lunch", 1, "new")
    assert any("extra roti" in event.mods for event in events)


@pytest.mark.parametrize(
    "text",
    ["kal lunch 2 nahi, 3 chahiye", "kal lunch 2 ki jagah 3 kar do"],
)
def test_restated_quantity_is_three_or_review(text):
    events = _events(text)
    assert (
        _order(events, "lunch", 3, "change")
        or _order(events, "lunch", 3, "new")
        or _reviewed(events)
    )
    if not _reviewed(events):
        assert not _order(events, "lunch", 2, "new")


def test_named_person_gets_a_plate_or_review():
    events = _events("kal lunch 1 thali, Priya ke liye bhi ek")
    matched = any(
        event.meal == "lunch" and event.qty == 2 and event.secondary_customer == "Priya"
        for event in events
    )
    assert matched or _reviewed(events)


def test_shaam_is_dinner_or_review():
    events = _events("kal shaam ko 1 thali")
    assert _order(events, "dinner", 1, "new") or _reviewed(events)
    if not _reviewed(events):
        assert not any(event.meal == "lunch" and event.action == "new" for event in events)


def test_question_is_not_an_order():
    events = _events("kal lunch? kitne baje aayega")
    assert _reviewed(events) or all(event.action in {"none", "pause"} for event in events)
    assert not any(event.action == "new" and not event.needs_review for event in events)


def test_cancel_one_thali_does_not_invent_a_meal():
    events = _events("Roommate left, cancel one thali from tomorrow")
    assert not any(
        event.action == "cancel" and event.meal == "lunch" and not event.needs_review
        for event in events
    )
    assert _reviewed(events) or any(
        event.action in {"change", "add"} and event.qty == 1 for event in events
    )


def test_garlic_and_onion_both_survive():
    events = _events("Aaj raat 1 thali, bina pyaaz lahsun.")
    assert _order(events, "dinner", 1, "new")
    mods = {mod for event in events for mod in event.mods}
    assert "no onion" in mods
    assert "no garlic" in mods


@pytest.mark.parametrize(
    "text,mod",
    [
        ("kal lunch 1, kam mirchi", "less spicy"),
        ("kal lunch 1 less oil please", "less oily"),
        ("bina pyaz kal lunch 1", "no onion"),
        ("pyaz nahi daalna kal lunch 1", "no onion"),
        ("kal lunch 1 extra chapati", "extra roti"),
    ],
)
def test_spelling_variants_become_canonical_mods(text, mod):
    events = _events(text)
    assert any(mod in event.mods and event.meal == "lunch" and event.qty == 1 for event in events)


@pytest.mark.parametrize(
    "text",
    [
        "kal lunch 1 peanut allergy please careful",
        "kal lunch 1, no sugar in anything, diabetic",
    ],
)
def test_unrecognised_request_reaches_the_cook(text):
    events = _events(text)
    assert any(
        event.needs_review and "unrecognised_request" in event.audit_flags for event in events
    )
    assert any(
        event.note and text.split(",")[0][:8].lower() in event.note.lower() for event in events
    )


@pytest.mark.parametrize(
    "text,qty",
    [("kal dono time ek ek", 1), ("kal dono time 2 2", 2)],
)
def test_both_meals_in_one_phrase(text, qty):
    events = _events(text)
    assert any(
        event.meal == "both" and event.qty == qty and event.action == "new" for event in events
    )


@pytest.mark.parametrize(
    "text",
    ["Monday to Friday lunch 1", "kal se ek hafte tak lunch 1 daily"],
)
def test_a_range_is_not_a_single_day_order(text):
    events = _events(text)
    assert _reviewed(events)
    assert not any(
        event.action == "new" and event.qty > 0 and not event.needs_review for event in events
    )


def test_huge_and_zero_quantities_stay_flagged():
    for text in ("kal lunch 100", "kal lunch 0"):
        events = _events(text)
        assert any(event.needs_review for event in events)


def test_a_later_note_keeps_the_earlier_one():
    state: dict = {}
    _apply_event(
        OrderEvent(
            customer="Ravi",
            date="2026-10-18",
            meal="lunch",
            qty=1,
            note="peanut allergy",
        ),
        state,
    )
    _apply_event(
        OrderEvent(
            customer="Ravi",
            date="2026-10-18",
            meal="lunch",
            qty=1,
            action="change",
            note="no sugar",
        ),
        state,
    )
    _apply_event(
        OrderEvent(
            customer="Ravi",
            date="2026-10-18",
            meal="lunch",
            qty=1,
            action="change",
            note="peanut allergy",
        ),
        state,
    )
    assert state[("ravi", "lunch")].notes == "peanut allergy; no sugar"
