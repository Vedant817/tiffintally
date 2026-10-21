"""Tests for durable SQLite persistence in tiffintally.db."""

import sqlite3
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from tiffintally.app import SESSIONS, app
from tiffintally.db import (
    get_connection,
    init_db,
    is_persistence_enabled,
    load_corrections,
    load_kitchen_events,
    mask_chat_text_for_storage,
    persist_correction,
    persist_upload_and_events,
)
from tiffintally.parser import split_sender
from tiffintally.schema import OrderEvent

REPO_ROOT = Path(__file__).resolve().parents[1]

# The export from the leak report: a bracketed WhatsApp export, so the first colon
# belongs to the timestamp and not to the sender.
BRACKETED_EXPORT = (
    "[17/10/2026, 9:00:00 pm] Rohan Kulkarni: kal lunch 2, roommate Sneha ke liye bhi 1\n"
    "[17/10/2026, 9:01:00 pm] Meera Iyer: kal dinner 1\n"
    "[17/10/2026, 9:02:00 pm] Rohan Kulkarni: delivery flat 402 Sai Heights, Baner Road\n"
    "[17/10/2026, 9:03:00 pm] Meera Iyer: 1600 gpay kiya, receipt sneha.iyer@example.com pe\n"
    "[17/10/2026, 9:04:00 pm] Rohan Kulkarni: number 9876543210 par ping karo\n"
    "[17/10/2026, 9:05:00 pm] Meera Iyer: mera number +91 91234 56789\n"
)

# None of these may survive in any persisted byte.
FORBIDDEN_IN_DB = (
    "9876543210",
    "91234 56789",
    "Rohan",
    "Kulkarni",
    "Meera",
    "Iyer",
    "Sneha",
    "example.com",
    "Sai Heights",
)


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

        # Verify loaded events. Stored names come back as tokens: the database
        # never held the real name, so it cannot give it back.
        loaded = load_kitchen_events("kitchen_test_123", db_path=db_path)
        assert len(loaded) == 2
        assert loaded[0].customer.startswith("C")
        assert loaded[0].meal == "lunch"
        assert loaded[0].qty == 2
        assert loaded[0].payment_amount == Decimal("160.00")
        assert loaded[1].customer.startswith("C")
        assert loaded[1].action == "cancel"


def test_persist_correction(monkeypatch, tmp_path):
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)

    # With the cwd pinned here, any write into the old shared
    # data/private/corrections.jsonl would land inside this sandbox and be seen.
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "test_tiffin.db"
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
        # Stored as a token, like every other customer field on disk.
        assert row["customer"].startswith("C")
        assert row["corrected_meal"] == "lunch"
        assert row["corrected_qty"] == 1

    # SQLite is the single durable store: persisting must not append two
    # kitchens' corrections into one shared JSONL under data/private/.
    assert not (tmp_path / "data" / "private" / "corrections.jsonl").exists()


def test_load_corrections_tolerates_only_a_missing_table(tmp_path, monkeypatch):
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)

    # an existing database that predates the corrections table reads as empty
    fresh = tmp_path / "fresh.db"
    with get_connection(fresh) as conn:
        conn.execute("CREATE TABLE placeholder (id INTEGER PRIMARY KEY)")
    assert load_corrections(fresh) == []

    # a database whose corrections table has a foreign schema (older layout
    # missing the columns a correction carries) must fail loudly: exporting an
    # empty batch while the durable corrections rust inside would look like a
    # successful export with nothing in it
    foreign = tmp_path / "foreign.db"
    with get_connection(foreign) as conn:
        conn.execute("CREATE TABLE corrections (id INTEGER PRIMARY KEY, kitchen_id TEXT)")
    with pytest.raises(sqlite3.OperationalError):
        load_corrections(foreign)


# --- the leak this file exists for ---------------------------------------------


def test_sender_comes_from_the_parser_not_the_first_colon():
    """A bracketed export's first colon is inside the timestamp."""
    assert split_sender("[17/10/2026, 9:00:00 pm] Rohan Kulkarni: kal lunch 2") == (
        "Rohan Kulkarni",
        "kal lunch 2",
    )
    assert split_sender("[17/10/2026, 9:00:00 pm] Messages and calls are encrypted") == (
        "SYSTEM",
        "Messages and calls are encrypted",
    )
    masked = mask_chat_text_for_storage("[17/10/2026, 9:00:00 pm] Rohan Kulkarni: kal lunch 2")
    assert "Rohan" not in masked and "Kulkarni" not in masked
    assert masked.startswith("[17/10/2026, 9:00:00 pm] C")


def _persisted_bytes(db_path: Path) -> bytes:
    """Every byte on disk for one database, including the WAL and shared memory."""
    parts = [db_path]
    parts += [Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]
    return b"".join(path.read_bytes() for path in parts if path.exists())


def test_bracketed_export_leaves_no_identifier_in_any_persisted_byte(monkeypatch):
    """Regression: the leak report's export must leave no name, phone or email."""
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "off")

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "leak.db"
        monkeypatch.setenv("TIFFINTALLY_DB_PATH", str(db_path))

        client = TestClient(app)
        response = client.post(
            "/process", data={"raw_text": BRACKETED_EXPORT, "target_date": "tomorrow"}
        )
        assert response.status_code == 200
        assert db_path.exists()

        with get_connection(db_path) as conn:
            tables = [
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            contents = {name: conn.execute(f"SELECT * FROM {name}").fetchall() for name in tables}

        # Not a vacuous scan: the upload and its orders really are on disk.
        assert contents["uploads"], "nothing was persisted, so the scan proves nothing"
        assert contents["orders"], "no order rows, so customer masking was never exercised"
        stored = {
            "orders.customer": [row["customer"] for row in contents["orders"]],
            "orders.secondary_customer": [row["secondary_customer"] for row in contents["orders"]],
            "orders.payment_note": [row["payment_note"] for row in contents["orders"]],
            "uploads.raw_text": [row["raw_text"] for row in contents["uploads"]],
        }
        assert any(value for value in stored["orders.secondary_customer"]), (
            "the fixture must produce a secondary customer for this test to mean anything"
        )
        assert any("gpay" in (note or "") for note in stored["orders.payment_note"]), (
            "the fixture must produce a payment note for this test to mean anything"
        )
        for field, values in stored.items():
            for value in values:
                assert not value or value.startswith("C") or "gpay" in value or "kal" in value, (
                    f"{field} looks unmasked: {value!r}"
                )

        blob = _persisted_bytes(db_path)
        leaked = [token for token in FORBIDDEN_IN_DB if token.encode() in blob]
        assert not leaked, f"identifier(s) written to disk: {leaked}"


def test_restored_session_says_the_names_are_tokens(monkeypatch):
    """A returning cook with persistence on must be told their names read as tokens.

    Stored names are tokens now, so the restored sheet cannot show a real name.
    Silently showing C001 looks like data loss; the note says what happened.
    """
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "off")

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "restore.db"
        monkeypatch.setenv("TIFFINTALLY_DB_PATH", str(db_path))

        cook = TestClient(app)
        response = cook.post(
            "/process",
            data={"raw_text": BRACKETED_EXPORT, "target_date": "tomorrow"},
            headers={"accept": "text/html"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        sid = cook.cookies.get("tt_sid")

        # A fresh browser with the same cookie: the session is gone, the rows are not.
        SESSIONS.pop(sid, None)
        returning = TestClient(app)
        returning.cookies.set("tt_sid", sid)
        prep = returning.get("/prep", headers={"accept": "text/html"})
        assert prep.status_code == 200
        assert "restored from database" in prep.text
        assert "Restored, not re-extracted" in prep.text
        assert "stored as tokens" in prep.text
        assert "names are tokens after restart" in prep.text.lower()
        for name in ("Rohan", "Kulkarni", "Meera", "Iyer", "Sneha"):
            assert name not in prep.text


def test_a_bare_street_name_is_not_masked_and_the_readme_says_so(monkeypatch):
    """Pinned boundary: flat numbers and the name after them go; a street alone stays.

    Widening the pattern to catch "Baner Road" would also swallow ordinary
    words in an order message, so the limit is documented instead of hidden.
    """
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "off")

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "street.db"
        monkeypatch.setenv("TIFFINTALLY_DB_PATH", str(db_path))
        client = TestClient(app)
        assert (
            client.post(
                "/process", data={"raw_text": BRACKETED_EXPORT, "target_date": "tomorrow"}
            ).status_code
            == 200
        )

        blob = _persisted_bytes(db_path)
        assert b"Baner Road" in blob, (
            "the street name is masked now; update README.md and drop this assertion"
        )
        assert b"Sai Heights" not in blob
        assert "street names can remain" in (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_every_file_under_data_is_scanned_including_private(monkeypatch, tmp_path):
    """Persistence is experimental. A session must not leave a real name on disk.

    The SQLite file is not the only write. Corrections land under data/private/.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "off")
    db_path = tmp_path / "data" / "kitchen.db"
    monkeypatch.setenv("TIFFINTALLY_DB_PATH", str(db_path))

    cook = TestClient(app)
    assert (
        cook.post(
            "/process", data={"raw_text": BRACKETED_EXPORT, "target_date": "tomorrow"}
        ).status_code
        == 200
    )
    saved = cook.post(
        "/api/corrections",
        json={
            "customer": "Rohan Kulkarni",
            "raw_text": "kal lunch 2, roommate Sneha ke liye bhi 1",
            "corrected_meal": "lunch",
            "corrected_qty": 2,
            "corrected_action": "new",
        },
    )
    assert saved.status_code == 200

    data_root = tmp_path / "data"
    files = [path for path in data_root.rglob("*") if path.is_file()]
    assert files, "a persist-mode session wrote nothing, so the scan proves nothing"
    assert any("private" in path.parts for path in files), "data/private/ was not scanned"
    blob = b"".join(path.read_bytes() for path in files)
    leaked = [token for token in FORBIDDEN_IN_DB if token.encode() in blob]
    assert not leaked, f"identifier(s) written under data/: {leaked}"
