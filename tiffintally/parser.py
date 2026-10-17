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


HEADER_PATTERNS = (
    ANDROID_HEADER_PATTERN,
    DOT_HEADER_PATTERN,
    ISO_HEADER_PATTERN,
    IOS_HEADER_PATTERN,
)


def header_match(line: str):
    """First header pattern that matches this line, or None."""
    cleaned = clean_text(line)
    for pattern in HEADER_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            return match
    return None


def split_sender(line: str) -> tuple[Optional[str], str]:
    """Sender and body of one export line, using the parser's own header rules.

    Returns (None, cleaned line) when the line is not a message header. Callers
    that need the sender of a whole export must use this rather than splitting
    on the first colon: in a bracketed export the first colon belongs to the
    timestamp ("[17/10/2026, 9:00:00 pm] Rohan: ..."), not to the sender.
    """
    match = header_match(line)
    if not match:
        return None, clean_text(line)
    remainder = match.groups()[2]
    if ":" in remainder:
        sender, body = remainder.split(":", 1)
        return clean_text(sender), clean_text(body)
    return "SYSTEM", clean_text(remainder)


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
        match = header_match(cleaned_line)
        if match:
            # New message header detected
            flush_current()

            d_str, t_str, _remainder = match.groups()
            parsed_ts = parse_datetime(d_str, t_str)
            current_timestamp = parsed_ts
            current_timestamp_unparsed = parsed_ts is None
            saw_header = True
            current_raw_lines.append(raw_line)

            # A colon separates sender from body; no colon means a system line.
            sender, message_body = split_sender(raw_line)
            if sender == "SYSTEM":
                current_sender = "SYSTEM"
                current_text_lines.append(message_body)
                current_is_system = True
            else:
                current_sender = sender or ""
                current_text_lines.append(message_body)
                current_is_system = False
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
