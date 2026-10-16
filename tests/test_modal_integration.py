"""Offline model transport: real serving parser, real client, controlled raw JSON."""

import json
from datetime import datetime

import httpx
import pytest

from scripts.modal_serve import _clean_event, _parse
from tiffintally.app import SESSION_COOKIE, SESSIONS, app
from tiffintally.extract.base import heuristic_extract, parse_and_validate_llm_json
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.reconcile import payment_id, reconcile_ledger
from tiffintally.schema import OrderEvent, ParsedMessage


def gold(**fields):
    return dict(
        date="tomorrow",
        meal="lunch",
        qty=2,
        action="new",
        items=["thali"],
        mods=["no onion"],
        confidence=0.95,
        **fields,
    )


def test_real_server_parser_preserves_all_fields():
    for index in range(20):
        row = gold(
            customer="C001",
            secondary_customer="Tanvi",
            secondary_qty=1,
            payment_amount=1500 + index,
            payment_note="received",
        )
        assert _parse(json.dumps({"events": [row]}))[0] == [row]


@pytest.mark.parametrize(
    "field,value",
    [("meal", "brunch"), ("action", "order"), ("qty", None), ("qty", 1.5), ("qty", True)],
)
def test_invalid_model_fields_cannot_become_orders(field, value):
    row = gold()
    row[field] = value
    clean = _clean_event(row)
    assert clean["invalid"]


def test_real_modal_client_sender_and_secondary_and_money(monkeypatch):
    extractor = GemmaExtractor(backend="modal", endpoint="https://mock.modal.run", token="test")
    messages = [
        ParsedMessage(
            sender="Karan",
            text="kal lunch 2 roommate Tanvi ke liye bhi ek",
            timestamp=datetime(2026, 10, 15, 20),
        ),
        ParsedMessage(
            sender="Vikram", text="1500 paid gpay", timestamp=datetime(2026, 10, 15, 20, 1)
        ),
    ]

    def post(payload):
        rows = [
            gold(customer="Wrong", secondary_customer="Tanvi"),
            dict(
                date="today",
                meal="unspecified",
                qty=0,
                action="payment",
                payment_amount=1500,
                payment_note="gpay",
                confidence=0.95,
            ),
        ]
        return httpx.Response(
            200,
            json={
                "model": "MOCK parser integration",
                "results": [_parse(json.dumps({"events": [row]}))[0] for row in rows],
            },
        )

    monkeypatch.setattr(extractor, "_post", post)
    events = extractor.extract_batch_counted(messages).events
    assert [event.customer for event in events] == ["Karan", "Vikram"]
    assert events[0].secondary_customer == "Tanvi"
    entry = reconcile_ledger(events)["vikram"]
    assert entry.total_claimed == 1500 and entry.total_paid == 0


@pytest.mark.parametrize(
    "flags,review", [([], True), (["prompt_injection"], False), (["any_audit_flag"], False)]
)
def test_confirmation_does_not_override_payment_safety(flags, review):
    event = OrderEvent(
        customer="Ravi",
        date="today",
        meal="unspecified",
        qty=0,
        action="payment",
        payment_amount=1500,
        audit_flags=flags,
        needs_review=review,
    )
    ledger = reconcile_ledger([event], confirmed_payments={payment_id(event)})
    assert "ravi" not in ledger


def test_confirmation_session_scope_idempotency_and_new_paste():
    from fastapi.testclient import TestClient

    with TestClient(app) as cook, TestClient(app) as visitor:
        cook.get("/prep")
        session = SESSIONS[cook.cookies.get(SESSION_COOKIE)]
        event = OrderEvent(
            customer="Ravi",
            date="today",
            meal="unspecified",
            qty=0,
            action="payment",
            payment_amount=1500,
        )
        session.events = [event]
        identity = payment_id(event)
        assert visitor.post(f"/api/payments/{identity}/confirm").status_code == 404
        for _ in range(2):
            assert cook.post(f"/api/payments/{identity}/confirm").status_code == 200
        assert (
            reconcile_ledger(session.events, confirmed_payments=session.confirmed_payments)[
                "ravi"
            ].total_paid
            == 1500
        )
        cook.post("/process", data={"raw_text": "", "target_date": "tomorrow"})
        assert not session.confirmed_payments


@pytest.mark.parametrize(
    "text", ["500 gpay kal kar dunga", "will pay 900 phonepe", "kal bhejunga 700"]
)
def test_future_promises_never_credit(text):
    assert not any(ev.action == "payment" for ev in heuristic_extract(text, "Ravi"))
    events, _ = parse_and_validate_llm_json(
        json.dumps(
            {"events": [dict(meal="unspecified", qty=0, action="payment", payment_amount=500)]}
        ),
        text,
        "Ravi",
    )
    assert not any(ev.action == "payment" for ev in events)


def test_order_and_payment_both_survive():
    events = heuristic_extract("kal lunch 2 paid 160 gpay", "Ravi")
    assert {ev.action for ev in events} == {"new", "payment"}
    assert next(ev for ev in events if ev.action == "new").qty == 2
    assert next(ev for ev in events if ev.action == "payment").payment_amount == 160
