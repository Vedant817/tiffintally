"""Tests for durable SQLite persistence in tiffintally.db."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from tiffintally.db import (
    get_connection,
    init_db,
    is_persistence_enabled,
    load_kitchen_events,
    persist_correction,
    persist_upload_and_events,
)
from tiffintally.schema import OrderEvent


def test_sqlite_persistence_gated_by_default(monkeypatch):
    """Persistence is off by default and off in demo mode."""
    monkeypatch.delenv("TIFFINTALLY_PERSIST", raising=False)
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    assert not is_persistence_enabled()

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tiffin.db"
        result = persist_upload_and_events(
            kitchen_id="kitchen_test_default",
            raw_text="Ravi: kal lunch 2 thali",
            filename="chat.txt",
            events=[],
            db_path=db_path,
        )
        assert result == ""
        assert not db_path.exists()

    # Demo mode forces persistence off even if TIFFINTALLY_PERSIST=1
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.setenv("TIFFINTALLY_DEMO_MODE", "true")
    assert not is_persistence_enabled()


def test_phone_number_never_appears_in_db_file(monkeypatch):
    """A pasted chat with a customer's phone number or address is masked before persistence."""
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    assert is_persistence_enabled()

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_privacy.db"
        phone_raw = "9876543210"
        phone_formatted = "+91 98765 43210"

        chat_paste = (
            f"12/10/2026, 21:30 - Priya ({phone_formatted}): kal lunch 2 thali flat 402 Shanti Apts\n"
            f"12/10/2026, 21:32 - {phone_raw}: kal dinner 1 thali"
        )

        events = [
            OrderEvent(
                customer=phone_formatted,
                raw_text=f"Priya ({phone_formatted}): kal lunch 2 thali flat 402",
                date="tomorrow",
                meal="lunch",
                qty=2,
                items=["thali"],
                mods=[],
                action="new",
                confidence=0.95,
            ),
            OrderEvent(
                customer=phone_raw,
                raw_text=f"{phone_raw}: kal dinner 1 thali",
                date="tomorrow",
                meal="dinner",
                qty=1,
                items=["thali"],
                mods=[],
                action="new",
                confidence=0.95,
            ),
        ]

        upload_id = persist_upload_and_events(
            kitchen_id="kitchen_privacy_check",
            raw_text=chat_paste,
            filename="whatsapp_export.txt",
            events=events,
            db_path=db_path,
        )

        assert upload_id != ""
        assert db_path.exists()

        # Binary check: raw phone digits must NEVER appear anywhere in the SQLite database file
        db_bytes = db_path.read_bytes()
        assert phone_raw.encode() not in db_bytes, (
            "Raw 10-digit phone number found in database file"
        )
        assert b"98765 43210" not in db_bytes, "Formatted phone number found in database file"
        assert b"Shanti Apts" not in db_bytes, "Street/apartment address found in database file"

        # Check DB records contain masked tokens (e.g. C001, C002)
        with get_connection(db_path) as conn:
            up_row = conn.execute(
                "SELECT raw_text FROM uploads WHERE id = ?", (upload_id,)
            ).fetchone()
            assert phone_raw not in up_row["raw_text"]
            assert phone_formatted not in up_row["raw_text"]

            order_rows = conn.execute(
                "SELECT customer, raw_text FROM orders WHERE upload_id = ?", (upload_id,)
            ).fetchall()
            for r in order_rows:
                assert phone_raw not in r["customer"]
                assert phone_formatted not in r["customer"]
                assert phone_raw not in r["raw_text"]
                assert phone_formatted not in r["raw_text"]


def test_sqlite_persistence_roundtrip(monkeypatch):
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)

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

        assert upload_id != ""

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


def test_persist_correction(monkeypatch):
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)

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
