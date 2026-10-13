"""Additional tests for deterministic reconciliation engine and dues ledger."""

from tiffintally.reconcile import reconcile_ledger, reconcile_orders
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
