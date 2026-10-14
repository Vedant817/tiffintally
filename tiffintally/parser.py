"""WhatsApp chat export parser supporting Android, iOS, 12h/24h formats and multiline messages."""

import re
from datetime import datetime
from typing import List, Optional

from tiffintally.schema import ParsedMessage

# Regex for Android WhatsApp message header:
# e.g.: "12/10/26, 10:14 pm - Sender: Message" or "12/10/2026, 22:14 - Sender: Message"
# Handles 1-2 digit month/day, 2-4 digit year, optional seconds, am/pm or 24h.
ANDROID_HEADER_PATTERN = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[aApP][mM])?)\s*-\s*(.+)$"
)

# Dot-separated dates seen in some Android exports: "13.10.26, 22:17 - Neha: ..."
DOT_HEADER_PATTERN = re.compile(
    r"^(\d{1,2}\.\d{1,2}\.\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[aApP][mM])?)\s*-\s*(.+)$"
)

# ISO local timestamps: "2026-10-13 22:18 - Amit: ..."
ISO_HEADER_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2}(?::\d{2})?(?:\s*[aApP][mM])?)\s*-\s*(.+)$"
)

# Regex for iOS WhatsApp message header:
# e.g.: "[12/10/26, 10:14:05 PM] Sender: Message" or "[12/10/2026, 22:14:05] Sender: Message"
IOS_HEADER_PATTERN = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[aApP][mM])?)\]\s*(.+)$"
)

MEDIA_MARKERS = [
    "<media omitted>",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "document omitted",
    "contact card omitted",
    "gif omitted",
    "voice message omitted",
]

# Full WhatsApp system phrases only. A bare "left" or "removed" also appears
# in real orders ("roommate left for home") and must not drop those lines.
SYSTEM_PATTERNS = [
    r"messages and calls are end-to-end encrypted",
    r"created group",
    r"added you",
    r"changed the subject",
    r"changed this group's icon",
    r"left the group",
    r"left this group",
    r"you left",
    r"was removed",
    r"you removed",
    r"removed you",
    r"security code changed",
    r"waiting for this message",
]


def clean_text(text: str) -> str:
    """Normalize unicode whitespace, strip LTR/RTL marks, and trim."""
    if not text:
        return ""
    # Strip invisible Unicode control marks (LTR mark \u200e, RTL mark \u200f)
    text = text.replace("\u200e", "").replace("\u200f", "")
    # Normalize narrow no-break space (\u202f) and non-breaking space (\xa0)
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    return text.strip()


def parse_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Parse a WhatsApp header. Return None when the header does not parse.

    Callers must flag that case. Substituting datetime.now() hides the order's real day.
    """
    date_str = clean_text(date_str)
    time_str = clean_text(time_str)

    # Normalize AM/PM spacing
    time_str = re.sub(r"\s*([aApP][mM])", r" \1", time_str).upper()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        date_formats = ["%Y-%m-%d"]
    else:
        date_str = date_str.replace(".", "/")
        date_formats = ["%d/%m/%y", "%d/%m/%Y", "%m/%d/%y", "%m/%d/%Y"]
    time_formats = ["%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"]

    for d_fmt in date_formats:
        for t_fmt in time_formats:
            fmt = f"{d_fmt} {t_fmt}"
            try:
                return datetime.strptime(f"{date_str} {time_str}", fmt)
            except ValueError:
                continue

    return None


def is_media_message(text: str) -> bool:
    """Check if the text represents an omitted media attachment."""
    cleaned = clean_text(text).lower()
    return any(marker in cleaned for marker in MEDIA_MARKERS)


def is_system_notification(text: str) -> bool:
    """Check if the line is a system generated notification."""
    cleaned = clean_text(text).lower()
    return any(re.search(pat, cleaned) for pat in SYSTEM_PATTERNS)


def parse_chat_export(content: str) -> List[ParsedMessage]:
    """
    Parse an entire WhatsApp exported chat file into structured ParsedMessage records.
    Correctly aggregates multiline messages and flags media/system records.
    """
    messages: List[ParsedMessage] = []
    lines = content.splitlines()

    current_timestamp: Optional[datetime] = None
    current_sender: Optional[str] = None
    current_text_lines: List[str] = []
    current_raw_lines: List[str] = []
    current_is_system = False
    current_timestamp_unparsed = False
    saw_header = False

    def flush_current():
        nonlocal \
            current_timestamp, \
            current_sender, \
            current_text_lines, \
            current_raw_lines, \
            current_is_system, \
            current_timestamp_unparsed, \
            saw_header
        if saw_header and (current_sender or current_is_system):
            full_text = "\n".join(current_text_lines).strip()
            raw_line = "\n".join(current_raw_lines).strip()
            is_media = is_media_message(full_text)
            messages.append(
                ParsedMessage(
                    timestamp=current_timestamp or datetime.min,
                    sender=current_sender or "SYSTEM",
                    text=full_text,
                    is_media=is_media,
                    is_system=current_is_system or is_system_notification(full_text),
                    raw_line=raw_line,
                    timestamp_unparsed=current_timestamp_unparsed or current_timestamp is None,
                )
            )
        current_text_lines = []
        current_raw_lines = []
        current_is_system = False
        current_timestamp_unparsed = False
        saw_header = False

    for raw_line in lines:
        cleaned_line = clean_text(raw_line)
        if not cleaned_line:
            if current_text_lines:
                current_text_lines.append("")
                current_raw_lines.append(raw_line)
            continue

        # Try Android, dot-date, ISO, then iOS.
        android_match = ANDROID_HEADER_PATTERN.match(cleaned_line)
        dot_match = DOT_HEADER_PATTERN.match(cleaned_line)
        iso_match = ISO_HEADER_PATTERN.match(cleaned_line)
        ios_match = IOS_HEADER_PATTERN.match(cleaned_line)

        match = android_match or dot_match or iso_match or ios_match
        if match:
            # New message header detected
            flush_current()

            d_str, t_str, remainder = match.groups()
            parsed_ts = parse_datetime(d_str, t_str)
            current_timestamp = parsed_ts
            current_timestamp_unparsed = parsed_ts is None
            saw_header = True
            current_raw_lines.append(raw_line)

            # Check if there is a sender separated by colon
            # e.g., "Ravi: Kal lunch 2" vs system line "Messages and calls are..."
            if ":" in remainder:
                parts = remainder.split(":", 1)
                current_sender = clean_text(parts[0])
                message_body = clean_text(parts[1])
                current_text_lines.append(message_body)
                current_is_system = False
            else:
                # System message line
                current_sender = "SYSTEM"
                current_text_lines.append(remainder)
                current_is_system = True
        else:
            # Continuation of previous message (multiline)
            if saw_header:
                current_text_lines.append(cleaned_line)
                current_raw_lines.append(raw_line)
            else:
                # Headerless paste. The clock time is unknown, so do not stamp "now".
                current_timestamp = None
                current_timestamp_unparsed = True
                saw_header = True
                current_sender = "Guest"
                current_text_lines.append(cleaned_line)
                current_raw_lines.append(raw_line)

    flush_current()
    return messages
