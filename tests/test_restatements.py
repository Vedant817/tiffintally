"""A re-stated order must change the count, not empty the sheet.

Two different counts from one name, one meal, one day is ambiguous: it is either
a customer correcting herself or two people saved under one display name. The
earlier code called that a conflict and withheld both rows, so "kal lunch 2"
followed by "kal lunch 3 kar do" produced lunch 0 for that customer and the cook
packed nothing for her.

The resolution applied here: use the later message, and flag the row so the cook
sees that the number moved.
"""

import pytest

from tiffintally.extract.base import heuristic_extract
from tiffintally.reconcile import reconcile_orders

AS_OF = "2026-10-16 06:00:00"


def _orders(text, customer, timestamp, meal="lunch"):
    events = heuristic_extract(text, customer)
    for e in events:
        e.timestamp = timestamp
        e.date = "2026-10-16"
        e.meal = meal
    return events


def _ev(customer, qty, timestamp, line_index, meal="lunch", date="2026-10-16"):
    from tiffintally.schema import OrderEvent

    return OrderEvent(
        customer=customer,
        date=date,
        meal=meal,
        qty=qty,
        items=["thali"],
        mods=[],
        action="new",
        timestamp=timestamp,
        line_index=line_index,
    )


def test_restated_order_applies_the_later_count():
    """The audit's repro: the sheet came up empty for a customer who corrected herself."""
    events = _orders("kal lunch 2", "Asha", "2026-10-15 20:00:00") + _orders(
        "kal lunch 3 kar do", "Asha", "2026-10-15 20:10:00"
    )

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    assert sheet.total_lunch == 3, "the later message is what she last said"


def test_restated_order_is_surfaced_for_review():
    """The cook is told the number moved, and the later count is still used.

    `needs_review` is deliberately NOT set here. That flag means "withhold this
    row", and withholding a restatement is the bug being fixed: the customer
    would vanish from the sheet again. The audit flag is what puts it in front of
    the cook.
    """
    events = _orders("kal lunch 2", "Asha", "2026-10-15 20:00:00") + _orders(
        "kal lunch 3 kar do", "Asha", "2026-10-15 20:10:00"
    )

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    restated = [ev for ev in sheet.unresolved_reviews if "restated" in ev.audit_flags]
    assert restated, "a changed count must reach the review list"
    assert sheet.total_lunch == 3, "surfaced and applied, not surfaced and withheld"


def test_restatement_does_not_use_the_conflict_flag():
    """Restated is not the same thing as same-minute-conflict.

    A conflict is withheld. A restatement is applied and shown. If the two were
    conflated the sheet would silently lose the customer again.
    """
    events = _orders("kal lunch 2", "Asha", "2026-10-15 20:00:00") + _orders(
        "kal lunch 3 kar do", "Asha", "2026-10-15 20:10:00"
    )

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    assert not [ev for ev in sheet.unresolved_reviews if "same_minute_conflict" in ev.audit_flags]


def test_a_real_same_minute_conflict_is_still_withheld():
    """Two counts stamped 20:00:00 cannot be ordered, so neither is applied."""
    events = [
        _ev("Asha", 2, "2026-10-15 20:00:00", 0),
        _ev("Asha", 5, "2026-10-15 20:00:00", 1),
    ]

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    assert sheet.total_lunch == 0
    flagged = [ev for ev in sheet.unresolved_reviews if "same_minute_conflict" in ev.audit_flags]
    assert len(flagged) == 2


def test_two_different_people_under_one_name_still_reach_the_cook():
    """The two-Priyas case is the reason the flag exists at all.

    Indistinguishable from a re-statement, so it gets the same treatment: the
    later count is packed and the cook is shown that it moved.
    """
    events = [
        _ev("Priya", 2, "2026-10-15 20:00:00", 0),
        _ev("Priya", 4, "2026-10-15 20:30:00", 1),
    ]

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    assert sheet.total_lunch == 4
    assert sheet.unresolved_reviews, "the cook must be told two names merged"


def test_an_unchanged_repeat_is_not_a_restatement():
    """The same count twice is a duplicate, not a change. Nothing to flag."""
    events = [
        _ev("Asha", 2, "2026-10-15 20:00:00", 0),
        _ev("Asha", 2, "2026-10-15 20:10:00", 1),
    ]

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    assert sheet.total_lunch == 2
    assert not [ev for ev in sheet.unresolved_reviews if "restated" in ev.audit_flags]


@pytest.mark.parametrize("second", ["kal lunch 3", "3 plate", "lunch 3"])
def test_restatement_survives_ordinary_phrasings(second):
    events = _orders("kal lunch 2", "Asha", "2026-10-15 20:00:00") + _orders(
        second, "Asha", "2026-10-15 20:10:00"
    )

    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)

    assert sheet.total_lunch == 3, second
