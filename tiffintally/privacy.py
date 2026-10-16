"""Privacy-preserving pseudonymisation before any text leaves the device.

What this claims and what it does: every display name the extractor has seen,
every phone number in any Indian spacing, and flat/house/gate numbers are
replaced with tokens before a message is sent to a hosted model. Anything it does
not recognise still leaves the device. That boundary is stated in the README
rather than glossed over as "names are masked".
"""

import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tiffintally.schema import OrderEvent

# Indian mobile numbers in the ways people actually type them:
# 9876543210, 98765 43210, +91-9876543210, 091-98765 43210, (98765) 43210.
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?91[\s().-]*|0)?[6-9](?:[\s().-]*\d){9}(?!\d)")

# A flat, house, plot or gate number. "flat 402 Shanti Apts" was going to Google
# intact while the claim in the README said addresses were masked.
ADDRESS_PATTERN = re.compile(
    r"\b(flat|house|h\.?\s*no|house\s*no|plot|shop|room|gate|floor|block|sector|building|"
    r"flatno|house\s*no)\b\.?\s*[-\#]?\s*\d{1,5}[a-zA-Z]?",
    re.IGNORECASE,
)

# A street or building name after a number, which the pattern above leaves.
ADDRESS_TAIL_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Z][a-z]+\s+(?:Apts|Apartments|Society|Complex|Heights|Nagar|Colony|"
    r"Park|Road|Lane|Block|Flats)\b"
)

EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")

# Names shorter than this are too generic to mask safely: "Ravi" is a person,
# "aunty" and "ji" are not, and masking them would corrupt the message.
MIN_NAME_LENGTH = 3


def normalized_identity(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return " ".join(
        "".join(
            character
            for character in text
            if unicodedata.category(character) not in {"Cf", "Co", "Cs"}
        ).split()
    )


class Pseudonymizer:
    """
    Replaces customer names, phone numbers and addresses with anonymous tokens
    (C001, C002) before sending text to a hosted model API.

    The default mapping lives only in this instance's memory. File persistence
    is an explicit library opt-in; the web app never opts in.
    """

    def __init__(self, db_path: Optional[Path] = None, known_names: Iterable[str] = ()):
        if db_path is None:
            self.db_path = Path(":memory:")
        elif str(db_path) == ":memory:":
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._cache: Dict[str, str] = {}
        self._reverse_cache: Dict[str, str] = {}
        self._init_db()
        self._load_cache()
        for name in known_names:
            if name and name.strip():
                self.register_senders([name])

    def _memory_conn(self) -> Optional[sqlite3.Connection]:
        """Held-open in-memory database, or None for a file-backed map."""
        return self._conn

    def _get_connection(self) -> sqlite3.Connection:
        if str(self.db_path) == ":memory:":
            # Each sqlite3.connect(":memory:") opens a *separate* empty database,
            # so the table created in _init_db would vanish on the next call.
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            return self._conn
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        conn = self._get_connection()
        try:
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
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

    def _load_cache(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT real_identifier, pseudo_id FROM customer_map")
            for real_id, pseudo_id in cur.fetchall():
                self._cache[normalized_identity(real_id).lower()] = pseudo_id
                self._reverse_cache[pseudo_id.upper()] = real_id

    def get_or_create_pseudo_id(self, real_identifier: str) -> str:
        """Return existing token for identifier or generate a new sequential token."""
        clean_id = real_identifier.strip()
        if not clean_id:
            return "C000"

        lookup_key = normalized_identity(clean_id).lower()
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

    def register_senders(self, senders: Iterable[str]) -> None:
        """Register every display name in an export, so bodies can be masked too.

        The first word is registered as an alias. WhatsApp shows "Asha Kulkarni"
        in the header but "Asha" in the message body, so masking only the full
        display name left the bare first name in the clear.
        """
        for sender in senders:
            if not sender or not sender.strip():
                continue
            self.get_or_create_pseudo_id(sender)
            first = sender.strip().split()[0] if sender.strip() else ""
            if len(first) >= MIN_NAME_LENGTH and first.lower() != sender.strip().lower():
                self.get_or_create_pseudo_id(first)

    def _known_names(self) -> List[str]:
        """Cached identifiers that look like a personal name.

        Anything registered through `register_senders` counts. Numbers and
        addresses are excluded: they are matched by their own patterns.
        """
        names = []
        for real_id in self._cache:
            if len(real_id) < MIN_NAME_LENGTH:
                continue
            if real_id.isdigit():
                continue
            if ADDRESS_PATTERN.match(real_id):
                continue
            names.append(real_id)
        return sorted(names, key=len, reverse=True)

    def mask_text(self, sender: str, text: str) -> Tuple[str, str]:
        """
        Mask the sender, every known customer name, phone numbers, addresses and
        emails in the text body.

        Returns (pseudo_sender, masked_text).
        """
        self.register_senders([sender])
        pseudo_sender = self.get_or_create_pseudo_id(sender)

        masked = normalized_identity(text)

        # Emails first: they can contain digits that look like a phone number.
        for match in EMAIL_PATTERN.findall(masked):
            masked = masked.replace(match, self.get_or_create_pseudo_id(match))

        # Phones next, before names, so "Asha 9876543210" does not become
        # "C001 C002" and then fail the name pass.
        for match in PHONE_PATTERN.findall(masked):
            token = self.get_or_create_pseudo_id(match.strip())
            masked = masked.replace(match, token)

        for match in ADDRESS_TAIL_PATTERN.findall(masked):
            masked = masked.replace(match, self.get_or_create_pseudo_id(match.strip()))

        for match in list(ADDRESS_PATTERN.finditer(masked)):
            value = match.group(0)
            masked = masked.replace(value, self.get_or_create_pseudo_id(value.strip()))

        # Every registered sender name, wherever it appears in the body. The old
        # code only masked the sender of the current message, so "roommate Priya"
        # and "Asha ka order" went out in the clear.
        for real_name in self._known_names():
            pattern = re.compile(rf"\b{re.escape(real_name)}\b", re.IGNORECASE)
            masked = pattern.sub(self.get_or_create_pseudo_id(real_name), masked)

        return pseudo_sender, masked

    def depseudonymize_order_event(self, event: OrderEvent) -> OrderEvent:
        """Return a copy of OrderEvent with real customer and secondary_customer restored."""
        data = event.model_dump()
        data["customer"] = self.depseudonymize(event.customer)
        if event.secondary_customer:
            data["secondary_customer"] = self.depseudonymize(event.secondary_customer)
        return OrderEvent(**data)
