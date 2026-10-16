"""
Durable database persistence layer for TiffinTally.

Provides ACID transactional persistence using SQLite (WAL mode).
Ensures all raw uploads, extracted orders, ledger adjustments, and active learning
corrections are permanently stored to disk and survive server restarts.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from tiffintally.schema import OrderEvent

logger = logging.getLogger(__name__)

# Default database location in data/
DEFAULT_DB_DIR = Path("data")
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "tiffintally.db"


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
    """Durably record raw chat upload and extracted order events into SQLite."""
    import uuid

    upload_id = uuid.uuid4().hex
    init_db(db_path)

    with get_connection(db_path) as conn:
        # Ensure kitchen exists
        conn.execute(
            "INSERT OR IGNORE INTO kitchens (id, name) VALUES (?, ?)",
            (kitchen_id, f"Kitchen {kitchen_id[:8]}"),
        )
        # Record upload
        conn.execute(
            "INSERT INTO uploads (id, kitchen_id, filename, raw_text, msg_count) VALUES (?, ?, ?, ?, ?)",
            (upload_id, kitchen_id, filename or "paste", raw_text, len(events)),
        )
        # Record extracted orders
        for ev in events:
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
                    ev.customer,
                    ev.raw_text,
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
                    ev.secondary_customer,
                    float(ev.payment_amount) if ev.payment_amount is not None else None,
                    ev.payment_note,
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
    """Durably record active learning correction into SQLite and append to corrections.jsonl."""
    init_db(db_path)

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
                customer,
                raw_text,
                corrected_meal,
                corrected_qty,
                corrected_action,
                applied_count,
            ),
        )
        correction_id = cursor.lastrowid

    # Canonical active learning file: ensure data/private/corrections.jsonl is updated
    canonical_file = Path("data/private/corrections.jsonl")
    try:
        canonical_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "id": correction_id,
            "kitchen_id": kitchen_id,
            "customer": customer,
            "raw_text": raw_text,
            "corrected_meal": corrected_meal,
            "corrected_qty": corrected_qty,
            "corrected_action": corrected_action,
            "timestamp": datetime.now().isoformat(),
        }
        with open(canonical_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.warning(f"Could not append to canonical corrections.jsonl: {exc}")

    return correction_id or 0


def load_kitchen_events(kitchen_id: str, db_path: Optional[Path] = None) -> List[OrderEvent]:
    """Retrieve saved order events for a kitchen from SQLite."""
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
                payment_amount=Decimal(str(r["payment_amount"])) if r["payment_amount"] is not None else None,
                payment_note=r["payment_note"],
            )
        )
    return events
