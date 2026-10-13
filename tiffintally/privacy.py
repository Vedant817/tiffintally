"""Privacy-preserving client-side pseudonymization layer."""

import re
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Tuple

from tiffintally.schema import OrderEvent

DEFAULT_DB_PATH = Path("data/privacy_map.db")

# Regex to match 10-digit Indian phone numbers with optional +91 or leading 0
PHONE_PATTERN = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")


class Pseudonymizer:
    """
    Replaces customer names and phone numbers with anonymous tokens (e.g. C001, C002)
    before sending text to hosted model APIs. Keeps the mapping in a local SQLite database.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._cache: Dict[str, str] = {}
        self._reverse_cache: Dict[str, str] = {}
        self._load_cache()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_map (
                    real_identifier TEXT PRIMARY KEY,
                    pseudo_id TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _load_cache(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT real_identifier, pseudo_id FROM customer_map")
            for real_id, pseudo_id in cur.fetchall():
                self._cache[real_id.lower()] = pseudo_id
                self._reverse_cache[pseudo_id.upper()] = real_id

    def get_or_create_pseudo_id(self, real_identifier: str) -> str:
        """Return existing token for identifier or generate a new sequential token (C001, C002...)."""
        clean_id = real_identifier.strip()
        if not clean_id:
            return "C000"

        lookup_key = clean_id.lower()
        if lookup_key in self._cache:
            return self._cache[lookup_key]

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM customer_map")
            count = cur.fetchone()[0]
            new_pseudo_id = f"C{count + 1:03d}"

            cur.execute(
                "INSERT OR IGNORE INTO customer_map (real_identifier, pseudo_id) VALUES (?, ?)",
                (clean_id, new_pseudo_id),
            )
            conn.commit()

            self._cache[lookup_key] = new_pseudo_id
            self._reverse_cache[new_pseudo_id] = clean_id
            return new_pseudo_id

    def depseudonymize(self, pseudo_id: str) -> str:
        """Resolve pseudo ID back to original real name or number for local display."""
        clean_token = pseudo_id.strip().upper()
        return self._reverse_cache.get(clean_token, pseudo_id)

    def mask_text(self, sender: str, text: str) -> Tuple[str, str]:
        """
        Mask sender name and any customer names / phone numbers present in the text body.
        Returns (pseudo_sender, masked_text).
        """
        pseudo_sender = self.get_or_create_pseudo_id(sender)

        masked_text = text
        # Mask phone numbers first
        for phone_match in PHONE_PATTERN.finditer(text):
            raw_phone = phone_match.group(0)
            token = self.get_or_create_pseudo_id(raw_phone)
            masked_text = masked_text.replace(raw_phone, token)

        # Mask known customer names that might appear in text (e.g. "Priya ke liye bhi ek")
        for real_name, token in sorted(self._cache.items(), key=lambda x: len(x[0]), reverse=True):
            if len(real_name) > 2 and real_name in masked_text.lower():
                pattern = re.compile(re.escape(real_name), re.IGNORECASE)
                masked_text = pattern.sub(token, masked_text)

        return pseudo_sender, masked_text

    def depseudonymize_order_event(self, event: OrderEvent) -> OrderEvent:
        """Return a copy of OrderEvent with real customer and secondary_customer restored."""
        data = event.model_dump()
        data["customer"] = self.depseudonymize(event.customer)
        if event.secondary_customer:
            data["secondary_customer"] = self.depseudonymize(event.secondary_customer)
        return OrderEvent(**data)
