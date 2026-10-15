"""Reading a pasted or uploaded WhatsApp export safely.

A cook on a ₹8,000 Android phone will paste a 21 MB export, and an iOS export
arrives as a zip. Before this, any upload was read whole into memory and parsed
on the event loop: one 21.6 MB paste blocked the server for 56 seconds, and a
UTF-16 export silently produced an empty sheet.

The limits here exist so a bad upload fails fast with a message the cook can act
on, instead of taking the kitchen's web app down.
"""

import io
import logging
import zipfile
from typing import Tuple

logger = logging.getLogger(__name__)

# A single evening's orders group export. Generous for text, small enough that a
# runaway paste cannot exhaust memory.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024

# A WhatsApp zip holds chat.txt plus media. We read only the text member.
MAX_ZIP_MEMBER_BYTES = 5 * 1024 * 1024
MAX_ZIP_RATIO = 100
MAX_ZIP_MEMBERS = 200

TEXT_MEMBER_NAMES = ("chat.txt", "_chat.txt", "whatsapp chat with")


class UploadRejected(ValueError):
    """The upload cannot be read. `status` is what the cook's browser should see."""


def decode_chat_upload(data: bytes, filename: str = "") -> str:
    """Decode an export to text, or raise UploadRejected with a usable reason."""
    if not data:
        raise UploadRejected("That file is empty.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected(
            f"That file is {len(data) // (1024 * 1024)} MB. "
            f"The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB: export one chat at a time."
        )

    if filename.lower().endswith(".zip") or data[:2] == b"PK":
        data = _read_text_from_zip(data)

    return decode_text(data)


def _read_text_from_zip(data: bytes) -> bytes:
    """Pull the chat text member out of a WhatsApp export zip.

    Guards against a zip bomb: too many members, an oversized member, or a
    member whose uncompressed size dwarfs its compressed size.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_MEMBERS:
                raise UploadRejected(
                    f"That zip holds {len(infos)} files. Export chat without media."
                )

            candidates = [
                info
                for info in infos
                if not info.is_dir()
                and info.filename.lower().endswith(".txt")
                and any(name in info.filename.lower() for name in TEXT_MEMBER_NAMES)
            ]
            if not candidates:
                candidates = [
                    info
                    for info in infos
                    if not info.is_dir() and info.filename.lower().endswith(".txt")
                ]
            if not candidates:
                raise UploadRejected("No chat text found in that zip.")

            info = min(candidates, key=lambda i: i.filename.count("/"))
            if info.file_size > MAX_ZIP_MEMBER_BYTES:
                raise UploadRejected(
                    f"The chat text inside is {info.file_size // (1024 * 1024)} MB. "
                    "Export chat without media."
                )
            if info.compress_size > 0 and info.file_size / info.compress_size > MAX_ZIP_RATIO:
                raise UploadRejected("That zip expands too far. Export chat without media.")
            return archive.read(info)
    except UploadRejected:
        raise
    except zipfile.BadZipFile:
        raise UploadRejected("That zip could not be opened. Try exporting without media.")


def decode_text(data: bytes) -> str:
    """Decode bytes to text, detecting UTF-16 and a BOM.

    `errors="replace"` on UTF-16 turned the whole export into NUL characters and
    an empty prep sheet, which looked to the cook like a tool that had silently
    lost her orders.
    """
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")

    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")

    # A UTF-16 export with no BOM is mostly NUL bytes interleaved with ASCII.
    sample = data[:512]
    if sample and sample.count(b"\x00") > len(sample) // 4:
        return data.decode("utf-16-le" if data[1:2] == b"\x00" else "utf-16-be", errors="replace")

    return data.decode("utf-8", errors="replace")


def check_paste_size(text: str) -> Tuple[bool, str]:
    """(ok, message) for a pasted body."""
    size = len(text.encode("utf-8", errors="ignore"))
    if size > MAX_UPLOAD_BYTES:
        return False, (
            f"That paste is {size // (1024 * 1024)} MB. "
            f"The limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB: paste one chat at a time."
        )
    return True, ""
