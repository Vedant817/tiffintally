"""Reconstructed from AUDIT4; original auditor files were not supplied."""

import pytest

from tiffintally.extract.base import parse_and_validate_llm_json
from tiffintally.reconcile import reconcile_ledger
from tiffintally.schema import OrderEvent


@pytest.mark.xfail(strict=True, reason="T4-005 model must not select customer")
def test_sender_owns_model_event():
    events, _ = parse_and_validate_llm_json(
        '{"events":[{"customer":"Other","date":"tomorrow","meal":"lunch","qty":2,"action":"new"}]}',
        "kal lunch 2",
        "Sender",
    )
    assert events[0].customer == "Sender"


@pytest.mark.xfail(strict=True, reason="T4-009 flagged payment credits ledger")
def test_flagged_payment_never_credits():
    event = OrderEvent(
        customer="Sender",
        date="today",
        meal="unspecified",
        qty=0,
        action="payment",
        payment_amount=1500,
        needs_review=True,
    )
    ledger = reconcile_ledger([event])
    assert "sender" not in ledger or ledger["sender"].total_paid == 0
