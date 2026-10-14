"""Additional tests for deterministic reconciliation engine and dues ledger."""

from datetime import datetime

from tiffintally.extract.base import heuristic_extract
from tiffintally.reconcile import calendar_day, reconcile_ledger, reconcile_orders
from tiffintally.schema import OrderEvent


def test_reconcile_empty_events():
    sheet = reconcile_orders([], target_date="tomorrow")
    assert sheet.total_thalis == 0
    assert sheet.total_lunch == 0
    assert sheet.total_dinner == 0
    assert len(sheet.packing_labels) == 0


def test_reconcile_multiple_dates_filtering():
    events = [
        OrderEvent(customer="A", date="2026-10-15", meal="lunch", qty=1, action="new"),
        OrderEvent(customer="B", date="2026-10-16", meal="lunch", qty=2, action="new"),
    ]
    sheet_15 = reconcile_orders(events, target_date="2026-10-15")
    assert sheet_15.total_thalis == 1
    assert len(sheet_15.packing_labels) == 1
    assert sheet_15.packing_labels[0].customer == "A"
    assert [ev.customer for ev in sheet_15.other_days] == ["B"]

    sheet_16 = reconcile_orders(events, target_date="2026-10-16")
    assert sheet_16.total_thalis == 2
    assert len(sheet_16.packing_labels) == 1
    assert sheet_16.packing_labels[0].customer == "B"


def test_reconcile_only_payments():
    events = [
        OrderEvent(
            customer="Ravi",
            date="today",
            meal="unspecified",
            qty=0,
            action="payment",
            raw_text="500 sent",
            payment_amount=500.0,
        ),
    ]
    sheet = reconcile_orders(events, target_date="today")
    assert sheet.total_thalis == 0
    assert len(sheet.packing_labels) == 0

    ledger = reconcile_ledger(events, price_per_thali=80.0, previous_balances={"ravi": 600.0})
    assert ledger["ravi"].total_paid == 500.0
    assert ledger["ravi"].balance_due == 100.0


def test_reconcile_both_lunch_and_dinner():
    events = [
        OrderEvent(customer="Kavita", date="tomorrow", meal="both", qty=1, action="new"),
    ]
    sheet = reconcile_orders(events, target_date="tomorrow")
    assert sheet.total_lunch == 1
    assert sheet.total_dinner == 1
    assert sheet.total_thalis == 2
    assert len(sheet.packing_labels) == 2


def test_reconcile_ledger_reminders_formatting():
    events = [
        OrderEvent(customer="Sunil", date="tomorrow", meal="lunch", qty=2, action="new"),
    ]
    ledger = reconcile_ledger(events, price_per_thali=80.0, previous_balances={"sunil": 200.0})
    entry = ledger["sunil"]
    assert entry.total_orders == 2
    assert entry.total_billed == 360.0
    assert entry.balance_due == 360.0
    assert "Namaste Sunil ji!" in entry.draft_reminder
    assert "₹360" in entry.draft_reminder


def test_review_row_is_not_billed():
    events = [
        OrderEvent(
            customer="Guest",
            date="unspecified",
            meal="lunch",
            qty=2,
            action="new",
            needs_review=True,
            audit_flags=["date_unresolved"],
        )
    ]
    assert reconcile_ledger(events, price_per_thali=80.0) == {}


def test_target_box_accepts_tomorrow_typos():
    clock = datetime(2026, 10, 15, 8, 0)
    assert calendar_day("tomrw", clock).isoformat() == "2026-10-16"
    assert calendar_day("tmrw", clock).isoformat() == "2026-10-16"
    assert calendar_day("sunday", clock).isoformat() == "2026-10-18"


def test_range_pause_drops_standing_orders_only_inside_the_window():
    events = heuristic_extract(
        "going home for Diwali, Sunday se next Thursday tak band rakhna",
        "Ananya",
    )
    events[0].timestamp = "2026-10-14 20:14:00"
    standing = {"Ananya": 1, "Amit": 1}
    as_of = datetime(2026, 10, 14, 21, 0)
    sunday = reconcile_orders(
        events, target_date="2026-10-18", standing_orders=standing, as_of=as_of
    )
    assert [label.customer for label in sunday.packing_labels] == ["Amit"]
    friday = reconcile_orders(
        events, target_date="2026-10-23", standing_orders=standing, as_of=as_of
    )
    assert {label.customer for label in friday.packing_labels} == {"Ananya", "Amit"}
