"""Tests for client-side privacy pseudonymization."""

from pathlib import Path

from tiffintally.privacy import Pseudonymizer
from tiffintally.schema import OrderEvent


def test_pseudonymization_mapping(tmp_path: Path):
    db_file = tmp_path / "test_privacy.db"
    p = Pseudonymizer(db_path=db_file)

    token1 = p.get_or_create_pseudo_id("Ravi Kumar")
    assert token1 == "C001"
    # Idempotent
    assert p.get_or_create_pseudo_id("Ravi Kumar") == "C001"
    assert p.get_or_create_pseudo_id("ravi kumar") == "C001"

    token2 = p.get_or_create_pseudo_id("Priya Sharma")
    assert token2 == "C002"

    assert p.depseudonymize("C001") == "Ravi Kumar"
    assert p.depseudonymize("C002") == "Priya Sharma"


def test_mask_text_and_phones(tmp_path: Path):
    db_file = tmp_path / "test_privacy2.db"
    p = Pseudonymizer(db_path=db_file)

    p.get_or_create_pseudo_id("Priya")

    sender = "Ravi"
    msg = "Priya ke liye bhi ek tiffin bhejo, call on 9876543210"
    pseudo_sender, masked = p.mask_text(sender, msg)

    assert pseudo_sender == "C002"  # Priya was C001, Ravi is C002
    assert "C001" in masked  # Priya masked to C001
    assert "9876543210" not in masked  # Phone number masked


def test_depseudonymize_order_event(tmp_path: Path):
    db_file = tmp_path / "test_privacy3.db"
    p = Pseudonymizer(db_path=db_file)

    token_ravi = p.get_or_create_pseudo_id("Ravi")
    token_priya = p.get_or_create_pseudo_id("Priya")

    event = OrderEvent(
        customer=token_ravi,
        secondary_customer=token_priya,
        date="2026-10-14",
        meal="lunch",
        qty=2,
        action="new",
    )

    restored = p.depseudonymize_order_event(event)
    assert restored.customer == "Ravi"
    assert restored.secondary_customer == "Priya"
