"""
Durable database persistence layer for TiffinTally.

Provides ACID transactional persistence using SQLite (WAL mode).
Persistence is gated behind TIFFINTALLY_PERSIST=1 (off by default and off in demo mode).
When it is on, stored chat lines and stored names are masked through one
Pseudonymizer per upload. What that masks and what it does not is written down
in README.md; the test in tests/test_db_persistence.py pins both halves.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Generator, List, Optional

from tiffintally.parser import parse_chat_export, split_sender
from tiffintally.privacy import Pseudonymizer, referenced_people
from tiffintally.schema import OrderEvent

logger = logging.getLogger(__name__)

# Default database location in data/
DEFAULT_DB_DIR = Path("data")
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "tiffintally.db"


def is_persistence_enabled() -> bool:
    """Return True only when TIFFINTALLY_PERSIST=1 and NOT in demo mode."""
    if os.getenv("TIFFINTALLY_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return os.getenv("TIFFINTALLY_PERSIST", "0").strip().lower() in {"1", "true", "yes", "on"}


def mask_chat_text_for_storage(text: str, pseudonymizer: Optional[Pseudonymizer] = None) -> str:
    """Mask every stored line using the parser's sender, not the first colon.

    Splitting a line on its first ":" cut inside a bracketed export's
    timestamp ("[17/10/2026, 9:00:00 pm] Rohan: ..."), so the sender was never
    registered and the name stayed in the clear. Every sender and every
    roommate named in the text is registered on one pseudonymizer before the
    lines are masked, so a name, a phone number, an email or a flat number is
    replaced wherever in the upload it appears.
    """
    if not text:
        return ""
    p = pseudonymizer or Pseudonymizer()
    for message in parse_chat_export(text):
        if not message.is_system:
            p.register_senders([message.sender])
        p.register_senders(referenced_people(message.text))
    masked_lines = []
    for line in text.splitlines():
        sender, _body = split_sender(line)
        _pseudo_sender, masked_line = p.mask_text(sender or "Guest", line)
        masked_lines.append(masked_line)
    return "\n".join(masked_lines)


def mask_correction_fields(customer: str, raw_text: str) -> tuple[str, str]:
    """Token for the cook's correction log. A fresh map, so it may not match orders."""
    p = Pseudonymizer()
    p.register_senders([customer, *referenced_people(raw_text)])
    masked_customer = mask_identifier(customer, p) or ""
    _sender, masked_raw = p.mask_text(customer, raw_text)
    return masked_customer, masked_raw


def mask_identifier(value: Optional[str], p: Pseudonymizer) -> Optional[str]:
    """Mask a stored name, email or phone number with the upload's token map."""
    if not value:
        return value
    _pseudo, masked = p.mask_text(value, value)
    return masked


def get_db_path() -> Path:
    env_path = os.getenv("TIFFINTALLY_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


@contextmanager
def get_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        # Enable Write-Ahead Logging for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables with full transactional schemas."""
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS kitchens (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settings_json TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY,
                kitchen_id TEXT NOT NULL,
                filename TEXT,
                raw_text TEXT NOT NULL,
                msg_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id TEXT,
                kitchen_id TEXT NOT NULL,
                customer TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                target_date TEXT NOT NULL,
                meal TEXT NOT NULL,
                qty INTEGER NOT NULL,
                items_json TEXT DEFAULT '[]',
                mods_json TEXT DEFAULT '[]',
                action TEXT NOT NULL,
                is_late BOOLEAN DEFAULT 0,
                needs_review BOOLEAN DEFAULT 0,
                confidence REAL DEFAULT 1.0,
                audit_flags_json TEXT DEFAULT '[]',
                secondary_customer TEXT,
                payment_amount REAL,
                payment_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kitchen_id TEXT NOT NULL,
                customer TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                corrected_meal TEXT NOT NULL,
                corrected_qty INTEGER NOT NULL,
                corrected_action TEXT NOT NULL,
                applied_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ledger_balances (
                kitchen_id TEXT NOT NULL,
                customer TEXT NOT NULL,
                balance TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (kitchen_id, customer)
            );

            CREATE INDEX IF NOT EXISTS idx_orders_kitchen_date ON orders(kitchen_id, target_date);
            CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(kitchen_id, customer);
            CREATE INDEX IF NOT EXISTS idx_corrections_kitchen ON corrections(kitchen_id);
            """
        )


def persist_upload_and_events(
    kitchen_id: str,
    raw_text: str,
    filename: Optional[str],
    events: List[OrderEvent],
    db_path: Optional[Path] = None,
) -> str:
    """Durably record chat upload and extracted order events into SQLite.

    Gated behind TIFFINTALLY_PERSIST=1 (off by default and off in demo mode).
    Stores only masked text in uploads.raw_text and orders.raw_text.
    """
    if not is_persistence_enabled():
        return ""

    import uuid

    upload_id = uuid.uuid4().hex
    init_db(db_path)

    # One token map for the whole upload, so a customer named in the chat, in an
    # order row and in a payment note all resolve to the same token.
    p = Pseudonymizer()
    stored_upload_text = mask_chat_text_for_storage(raw_text, p)

    with get_connection(db_path) as conn:
        # Ensure kitchen exists
        conn.execute(
            "INSERT OR IGNORE INTO kitchens (id, name) VALUES (?, ?)",
            (kitchen_id, f"Kitchen {kitchen_id[:8]}"),
        )
        # Record upload (masked text only, never raw PII or raw phone numbers)
        conn.execute(
            "INSERT INTO uploads (id, kitchen_id, filename, raw_text, msg_count) VALUES (?, ?, ?, ?, ?)",
            (upload_id, kitchen_id, filename or "paste", stored_upload_text, len(events)),
        )
        # Record extracted orders (masked text only)
        for ev in events:
            masked_order_raw = mask_chat_text_for_storage(ev.raw_text, p)
            conn.execute(
                """
                INSERT INTO orders (
                    upload_id, kitchen_id, customer, raw_text, target_date,
                    meal, qty, items_json, mods_json, action,
                    is_late, needs_review, confidence, audit_flags_json,
                    secondary_customer, payment_amount, payment_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    kitchen_id,
                    mask_identifier(ev.customer, p),
                    masked_order_raw,
                    ev.date or "tomorrow",
                    ev.meal,
                    ev.qty,
                    json.dumps(ev.items or []),
                    json.dumps(ev.mods or []),
                    ev.action,
                    1 if ev.is_late else 0,
                    1 if ev.needs_review else 0,
                    float(ev.confidence or 1.0),
                    json.dumps(ev.audit_flags or []),
                    mask_identifier(ev.secondary_customer, p),
                    float(ev.payment_amount) if ev.payment_amount is not None else None,
                    mask_identifier(ev.payment_note, p),
                ),
            )

    return upload_id


def persist_correction(
    kitchen_id: str,
    customer: str,
    raw_text: str,
    corrected_meal: str,
    corrected_qty: int,
    corrected_action: str,
    applied_count: int = 1,
    db_path: Optional[Path] = None,
) -> int:
    """Durably record an active learning correction into SQLite.

    The corrections table (keyed by `kitchen_id`) is the single durable store.
    Nothing is appended to a shared canonical JSONL here: connecting every
    kitchen's corrections into one file is exactly the pooling the per-session
    corrections files exist to prevent.
    """
    if not is_persistence_enabled():
        return 0

    init_db(db_path)
    customer_clean, masked_raw = mask_correction_fields(customer, raw_text)

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO corrections (
                kitchen_id, customer, raw_text, corrected_meal, corrected_qty,
                corrected_action, applied_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kitchen_id,
                customer_clean,
                masked_raw,
                corrected_meal,
                corrected_qty,
                corrected_action,
                applied_count,
            ),
        )
        correction_id = cursor.lastrowid

    return correction_id or 0


def load_kitchen_events(kitchen_id: str, db_path: Optional[Path] = None) -> List[OrderEvent]:
    """Retrieve saved order events for a kitchen from SQLite."""
    if not is_persistence_enabled():
        return []

    path = db_path or get_db_path()
    if not path.exists():
        return []

    init_db(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE kitchen_id = ? ORDER BY id ASC",
            (kitchen_id,),
        ).fetchall()

    events: List[OrderEvent] = []
    for r in rows:
        events.append(
            OrderEvent(
                customer=r["customer"],
                raw_text=r["raw_text"],
                date=r["target_date"],
                meal=r["meal"],
                qty=r["qty"],
                items=json.loads(r["items_json"] or "[]"),
                mods=json.loads(r["mods_json"] or "[]"),
                action=r["action"],
                is_late=bool(r["is_late"]),
                needs_review=bool(r["needs_review"]),
                confidence=r["confidence"],
                audit_flags=json.loads(r["audit_flags_json"] or "[]"),
                secondary_customer=r["secondary_customer"],
                payment_amount=Decimal(str(r["payment_amount"]))
                if r["payment_amount"] is not None
                else None,
                payment_note=r["payment_note"],
            )
        )
    return events


def load_corrections(db_path: Optional[Path] = None) -> List[dict]:
    """Load every recorded correction from the durable store, all kitchens together.

    The corrections table (keyed by `kitchen_id`) is the single durable store
    for corrections; this is the explicit read-side combiner a training run
    needs if it wants them in one batch again. Returns one dict per row
    (`kitchen_id`, `customer`, `raw_text`, `corrected_meal`, `corrected_qty`,
    `corrected_action`, `created_at`), empty when persistence is off, the file
    is absent or the table does not exist yet.
    """
    if not is_persistence_enabled():
        return []

    path = db_path or get_db_path()
    if not path.exists():
        return []

    with get_connection(path) as conn:
        try:
            rows = conn.execute(
                "SELECT kitchen_id, customer, raw_text, corrected_meal, corrected_qty,"
                " corrected_action, created_at FROM corrections ORDER BY id ASC"
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    return [dict(r) for r in rows]
