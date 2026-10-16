"""Tests for durable SQLite persistence in tiffintally.db."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from tiffintally.db import (
    get_connection,
    init_db,
    load_kitchen_events,
    persist_correction,
    persist_upload_and_events,
)
from tiffintally.schema import OrderEvent


def test_sqlite_persistence_roundtrip():
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tiffin.db"
        init_db(db_path)

        events = [
            OrderEvent(
                customer="Ravi Sharma",
                raw_text="kal lunch 2 thali",
                date="tomorrow",
                meal="lunch",
                qty=2,
                items=["thali"],
                mods=["spicy"],
                action="new",
                confidence=0.95,
                payment_amount=Decimal("160.00"),
            ),
            OrderEvent(
                customer="Anita P",
                raw_text="dinner cancel",
                date="tomorrow",
                meal="dinner",
                qty=0,
                items=[],
                mods=[],
                action="cancel",
                confidence=1.0,
            ),
        ]

        upload_id = persist_upload_and_events(
            kitchen_id="kitchen_test_123",
            raw_text="Ravi: kal lunch 2 thali\nAnita: dinner cancel",
            filename="chat_export.txt",
            events=events,
            db_path=db_path,
        )

        assert upload_id is not None

        # Verify raw upload in db
        with get_connection(db_path) as conn:
            up_row = conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
            assert up_row is not None
            assert up_row["kitchen_id"] == "kitchen_test_123"
            assert up_row["msg_count"] == 2

        # Verify loaded events
        loaded = load_kitchen_events("kitchen_test_123", db_path=db_path)
        assert len(loaded) == 2
        assert loaded[0].customer == "Ravi Sharma"
        assert loaded[0].meal == "lunch"
        assert loaded[0].qty == 2
        assert loaded[0].payment_amount == Decimal("160.00")
        assert loaded[1].customer == "Anita P"
        assert loaded[1].action == "cancel"


def test_persist_correction():
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tiffin.db"
        cid = persist_correction(
            kitchen_id="kitchen_corr_test",
            customer="Vikram",
            raw_text="kal ek thali",
            corrected_meal="lunch",
            corrected_qty=1,
            corrected_action="new",
            applied_count=1,
            db_path=db_path,
        )
        assert cid > 0

        with get_connection(db_path) as conn:
            row = conn.execute("SELECT * FROM corrections WHERE id = ?", (cid,)).fetchone()
            assert row is not None
            assert row["customer"] == "Vikram"
            assert row["corrected_meal"] == "lunch"
            assert row["corrected_qty"] == 1
