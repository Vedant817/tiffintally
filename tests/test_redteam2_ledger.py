"""Phase 2: the bill must follow the reconciled sheet, not the sum of messages.

A cook who copies the drafted reminder sends it to the customer. If the ledger
says five thalis when the sheet says three, the first use of the product is a
wrong bill.
"""

from datetime import datetime, time

import pytest

from tiffintally.extract.base import heuristic_extract
from tiffintally.reconcile import payment_id, reconcile_ledger, reconcile_orders
from tiffintally.schema import OrderEvent

AS_OF = datetime(2026, 10, 15, 21, 0)


def ev(**kwargs) -> OrderEvent:
    """An order event with sensible defaults, so each test reads as one line."""
    base = {
        "customer": "Asha",
        "date": "2026-10-16",
        "meal": "lunch",
        "qty": 1,
        "action": "new",
    }
    base.update(kwargs)
    return OrderEvent(**base)


# --- F6: the ledger follows the final state -----------------------------------


def test_change_to_three_bills_three_not_five():
    """'kal lunch 2' then 'change to 3' is three plates, not 2 + 3."""
    events = [
        ev(qty=2, timestamp="2026-10-15 20:00:00"),
        ev(qty=3, action="change", timestamp="2026-10-15 20:30:00"),
    ]
    ledger = reconcile_ledger(events, price_per_thali=80.0)
    entry = ledger["asha"]
    assert entry.total_orders == 3
    assert entry.total_billed == 240.0
    assert entry.balance_due == 240.0


def test_cancelled_meal_is_not_billed():
    events = [
        ev(qty=1, timestamp="2026-10-15 20:00:00"),
        ev(qty=0, action="cancel", timestamp="2026-10-15 20:30:00"),
    ]
    ledger = reconcile_ledger(events, price_per_thali=80.0)
    entry = ledger["asha"]
    assert entry.total_orders == 0
    assert entry.balance_due == 0.0
    assert entry.draft_reminder == ""


def test_cancel_before_cutoff_is_billed_as_zero():
    """'kal lunch 1' then 'cancel' at 21:00, cutoff 22:00: still zero."""
    events = [
        ev(qty=1, timestamp="2026-10-15 20:00:00"),
        ev(qty=0, action="cancel", timestamp="2026-10-15 21:00:00"),
    ]
    ledger = reconcile_ledger(events, price_per_thali=80.0)
    assert ledger["asha"].balance_due == 0.0


def test_pause_removes_the_days():
    events = [
        ev(qty=1, date="2026-10-16", timestamp="2026-10-15 20:00:00"),
        ev(qty=1, date="2026-10-17", timestamp="2026-10-15 20:00:00"),
        ev(qty=0, action="pause", date="2026-10-17", timestamp="2026-10-15 20:10:00"),
    ]
    ledger = reconcile_ledger(events, price_per_thali=80.0)
    assert ledger["asha"].total_orders == 1
    assert ledger["asha"].balance_due == 80.0


def test_partial_payment_reduces_the_balance():
    events = [
        ev(qty=2, timestamp="2026-10-15 20:00:00"),
        ev(qty=0, action="payment", payment_amount=100.0, timestamp="2026-10-15 20:10:00"),
    ]
    entry = reconcile_ledger(
        events, price_per_thali=80.0, confirmed_payments={payment_id(events[1])}
    )["asha"]
    assert entry.total_billed == 160.0
    assert entry.total_paid == 100.0
    assert entry.balance_due == 60.0


def test_previous_balance_carries_over():
    events = [ev(qty=1, timestamp="2026-10-15 20:00:00")]
    entry = reconcile_ledger(events, price_per_thali=80.0, previous_balances={"asha": 250.0})[
        "asha"
    ]
    assert entry.balance_due == 330.0


def test_ledger_and_sheet_agree_on_total_plates():
    """The invariant that matters: what is billed is what was packed."""
    events = [
        ev(customer="Asha", qty=2, timestamp="2026-10-15 20:00:00"),
        ev(customer="Asha", qty=3, action="change", timestamp="2026-10-15 20:30:00"),
        ev(customer="Ravi", qty=1, timestamp="2026-10-15 20:05:00"),
        ev(customer="Ravi", qty=0, action="cancel", timestamp="2026-10-15 21:00:00"),
    ]
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    ledger = reconcile_ledger(events, price_per_thali=80.0)
    billed_thalis = sum(e.total_orders for e in ledger.values())
    assert sheet.total_thalis == billed_thalis
    assert billed_thalis == 3


# --- M2: late cancels reduce waste --------------------------------------------


def test_late_cancel_is_shown_as_a_pending_reduction():
    """At 23:15 the cook has not started. A late cancel should be offered."""
    events = [
        ev(qty=2, timestamp="2026-10-15 20:00:00"),
        ev(qty=0, action="cancel", timestamp="2026-10-15 23:15:00"),
    ]
    sheet = reconcile_orders(
        events,
        target_date="2026-10-16",
        cutoff_time=time(22, 0),
        as_of=AS_OF,
    )
    assert sheet.total_lunch == 2
    assert sheet.late_cancellations, "a late cancel must be visible, not dropped"
    assert sheet.late_cancellations[0].qty == 0


def test_late_cancel_sheet_offers_accept():
    events = [
        ev(qty=2, timestamp="2026-10-15 20:00:00"),
        ev(qty=0, action="cancel", timestamp="2026-10-15 23:15:00"),
    ]
    sheet = reconcile_orders(
        events,
        target_date="2026-10-16",
        cutoff_time=time(22, 0),
        as_of=AS_OF,
        accept_late_cancels=True,
    )
    assert sheet.total_lunch == 0


def test_late_add_stays_pending():
    """A late extra plate needs the cook's yes, so it is not silently added."""
    events = [
        ev(qty=1, timestamp="2026-10-15 20:00:00"),
        ev(qty=2, action="change", timestamp="2026-10-15 23:00:00"),
    ]
    sheet = reconcile_orders(
        events,
        target_date="2026-10-16",
        cutoff_time=time(22, 0),
        as_of=AS_OF,
    )
    assert sheet.total_lunch == 1
    assert len(sheet.late_orders) == 1


# --- M3: after midnight --------------------------------------------------------


def test_post_midnight_message_lands_on_the_previous_day_sheet():
    """00:30 on the 16th is the evening of the 15th: "kal" means the 16th."""
    events = [
        ev(qty=2, timestamp="2026-10-16 00:30:00", date="tomorrow"),
    ]
    sheet = reconcile_orders(
        events,
        target_date="2026-10-16",
        cutoff_time=time(22, 0),
        as_of=datetime(2026, 10, 16, 8, 0),
    )
    assert sheet.date == "2026-10-16"
    assert not sheet.other_days, "the order belongs to the 16th, not the 17th"
    assert sheet.unresolved_reviews, "an after-midnight order needs a look"
    assert sheet.late_orders, "00:30 is after a 22:00 cutoff, not before it"


def test_after_midnight_message_counts_as_after_cutoff():
    """00:30 must not slip past a 22:00 cutoff just because the clock wrapped."""
    events = [ev(qty=1, timestamp="2026-10-15 23:50:00", date="2026-10-16")]
    sheet = reconcile_orders(
        events,
        target_date="2026-10-16",
        cutoff_time=time(22, 0),
        as_of=datetime(2026, 10, 16, 8, 0),
    )
    assert sheet.late_orders, "a 23:50 order is after a 22:00 cutoff"
    assert sheet.total_lunch == 0


# --- M4: order independence ----------------------------------------------------


def test_shuffling_same_minute_events_gives_the_same_sheet():
    """Android exports have minute precision, so two orders can share a stamp.

    `line_index` travels with the event, so shuffling the list cannot change the
    outcome. Before this, seed 0 gave lunch 0 and seeds 1-3 gave lunch 2.
    """
    import random

    base = [
        ev(customer="Asha", qty=2, timestamp="2026-10-15 20:00:00", line_index=0),
        ev(customer="Ravi", qty=1, timestamp="2026-10-15 20:00:00", line_index=1),
        ev(customer="Ravi", qty=4, action="change", timestamp="2026-10-15 20:00:00", line_index=2),
    ]
    expected = reconcile_orders(base, target_date="2026-10-16", as_of=AS_OF)
    for seed in range(20):
        shuffled = base[:]
        random.Random(seed).shuffle(shuffled)
        got = reconcile_orders(shuffled, target_date="2026-10-16", as_of=AS_OF)
        assert got.total_lunch == expected.total_lunch, f"seed {seed}"
        assert got.packing_labels == expected.packing_labels, f"seed {seed}"


def test_same_minute_conflict_is_flagged_for_review():
    events = [
        ev(customer="Asha", qty=2, timestamp="2026-10-15 20:00:00"),
        ev(customer="Asha", qty=5, action="change", timestamp="2026-10-15 20:00:00"),
    ]
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    assert sheet.unresolved_reviews, "two different counts in one minute needs a human"


# --- M5: "ek aur" and the cook's own messages ---------------------------------


def test_one_more_adds_to_the_order():
    events = [
        ev(qty=2, timestamp="2026-10-15 20:00:00"),
        ev(qty=1, action="add", timestamp="2026-10-15 20:10:00"),
    ]
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    assert sheet.total_lunch == 3


def test_plus_one_adds_to_the_order():
    events = [
        ev(qty=2, timestamp="2026-10-15 20:00:00"),
        ev(qty=1, action="add", timestamp="2026-10-15 20:10:00"),
    ]
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    assert sheet.total_lunch == 3


def test_cook_messages_are_never_counted():
    """In a group the cook's 'ok kal lunch 2 done' is not a customer order."""
    events = [
        ev(customer="Asha", qty=2, timestamp="2026-10-15 20:00:00"),
        ev(customer="Ravi", qty=1, timestamp="2026-10-15 20:01:00"),
        ev(customer="Sunita Aunty (cook)", qty=2, timestamp="2026-10-15 20:02:00"),
    ]
    sheet = reconcile_orders(
        events,
        target_date="2026-10-16",
        as_of=AS_OF,
        cook_names=["Sunita Aunty (cook)"],
    )
    assert sheet.total_lunch == 3


def test_conflicting_orders_under_one_display_name_are_flagged():
    """Two people saved as 'Priya' merge into one key. The cook must be told."""
    events = [
        ev(customer="Priya", qty=2, timestamp="2026-10-15 20:00:00", line_index=0),
        ev(customer="Priya", qty=4, timestamp="2026-10-15 20:30:00", line_index=1),
    ]
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    assert sheet.unresolved_reviews


@pytest.mark.parametrize(
    "text,expected",
    [
        ("kal lunch 2", 2),
        ("kal lunch 2, aur ek bhej dena", 3),
        ("kal lunch ek aur bhej dena", 1),
    ],
)
def test_delta_phrasing_in_one_message(text, expected):
    events = heuristic_extract(text, "Asha")
    for e in events:
        e.timestamp = "2026-10-15 20:00:00"
        e.date = "2026-10-16"
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    assert sheet.total_lunch == expected


@pytest.mark.parametrize("delta_text", ["kal lunch ek aur", "+1 kal lunch", "1 more kal lunch"])
def test_one_more_in_a_later_message_adds_to_the_order(delta_text):
    """ "lunch 2" then "ek aur" is three plates, not one.

    The delta arrived as its own message, so it has to add to the order already
    on the sheet instead of replacing it.
    """
    events = []
    for index, text in enumerate(("kal lunch 2", delta_text)):
        for e in heuristic_extract(text, "Asha"):
            e.timestamp = "2026-10-15 20:0%d:00" % index
            e.line_index = index
            e.date = "2026-10-16"
            events.append(e)
    sheet = reconcile_orders(events, target_date="2026-10-16", as_of=AS_OF)
    assert sheet.total_lunch == 3
