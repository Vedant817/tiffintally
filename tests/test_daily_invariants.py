"""Cross-projection properties and round-four calendar regressions."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from tiffintally.reconcile import plates_by_day, reconcile_ledger, reconcile_orders
from tiffintally.schema import OrderEvent

AS_OF = datetime(2026, 10, 15, 20)


def event(**changes):
    row = dict(
        customer="Ravi",
        date="tomorrow",
        meal="lunch",
        qty=2,
        action="new",
        timestamp="2026-10-15 20:00:00",
    )
    row.update(changes)
    return OrderEvent(**row)


def test_ten_evenings_bill_twenty_plates():
    events = [event(timestamp=(AS_OF + timedelta(days=i)).isoformat()) for i in range(10)]
    assert reconcile_ledger(events, as_of=AS_OF)["ravi"].total_orders == 20
    assert len(plates_by_day(events, as_of=AS_OF)) == 10


def test_call_order_cannot_change_events_or_bill():
    events = [event(), event(qty=3, timestamp="2026-10-15 20:10:00")]
    snapshot = [row.model_dump() for row in events]
    first = reconcile_ledger(events, as_of=AS_OF)
    assert reconcile_orders(events, as_of=AS_OF).total_lunch == 3
    assert reconcile_ledger(events, as_of=AS_OF) == first
    assert [row.model_dump() for row in events] == snapshot


def test_exact_paise_and_opening_only_balance():
    ledger = reconcile_ledger(
        [event(qty=1)],
        price_per_thali="0.10",
        previous_balances={"Ravi": "33.23", "Mira": "0.10"},
        as_of=AS_OF,
    )
    assert ledger["ravi"].balance_due == Decimal("33.33")
    assert "₹33.33" in ledger["ravi"].draft_reminder
    assert ledger["mira"].balance_due == Decimal("0.10")


def test_secondary_share_is_part_of_total():
    events = [event(qty=5, secondary_customer="Tanvi", secondary_qty=2)]
    sheet = reconcile_orders(events, as_of=AS_OF)
    assert {label.customer: label.qty for label in sheet.packing_labels} == {"Ravi": 3, "Tanvi": 2}
    assert sum(row.total_orders for row in reconcile_ledger(events, as_of=AS_OF).values()) == 5


def test_balance_csv_and_explicit_alias_confirmation():
    from fastapi.testclient import TestClient

    from tiffintally.app import SESSION_COOKIE, SESSIONS, app

    with TestClient(app) as cook:
        cook.post(
            "/process",
            data={
                "raw_text": "15/10/26, 8:00 pm - Ravi: kal lunch 2\n"
                "15/10/26, 8:10 pm - Ravi Kumar: kal lunch 3",
                "target_date": "2026-10-16",
                "price_per_thali": "33.33",
            },
        )
        session = SESSIONS[cook.cookies.get(SESSION_COOKIE)]
        assert session.sheet.total_thalis == 5
        assert "Merge Ravi into Ravi Kumar?" in cook.get("/ledger").text
        assert (
            cook.post(
                "/api/aliases/confirm", data={"source": "Ravi", "target": "Ravi Kumar"}
            ).status_code
            == 200
        )
        assert session.sheet.total_thalis == 3
        upload = cook.post(
            "/ledger/balances",
            files={"balance_file": ("balances.csv", b"customer,balance\nRavi Kumar,0.10\n")},
        )
        assert upload.status_code == 200
        text = cook.get("/ledger/balances.csv").text
        assert "Ravi Kumar,100.09" in text
        cook.post(
            "/ledger/balances",
            files={"balance_file": ("bad.csv", b"customer,balance\nRavi Kumar,NaN\n")},
        )
        assert cook.get("/ledger/balances.csv").text == text


@settings(max_examples=500, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["new", "change", "add", "cancel", "pause"]),
            st.integers(0, 10),
            st.integers(0, 23),
            st.sampled_from(["lunch", "dinner", "both"]),
        ),
        max_size=20,
    ),
    st.booleans(),
)
def test_sheet_equals_daily_ledger(rows, accept):
    events = [
        event(
            action=action, qty=qty, meal=meal, line_index=i, timestamp=f"2026-10-15 {hour:02}:00:00"
        )
        for i, (action, qty, hour, meal) in enumerate(rows)
    ]
    options = dict(
        as_of=AS_OF, target_date="2026-10-16", cutoff_time=time(22), accept_late_cancels=accept
    )
    snapshot = [ev.model_dump() for ev in events]
    sheet = reconcile_orders(events, **options)
    ledger = reconcile_ledger(events, **options)
    assert sheet.total_thalis == sum(row.total_orders for row in ledger.values())
    assert [ev.model_dump() for ev in events] == snapshot
