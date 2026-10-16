"""Phase 3: what a stranger can reach, read, or write through the app.

Every case here was reachable before this phase.
"""

import io
import zipfile
from datetime import datetime

import pytest
from starlette.testclient import TestClient

from tiffintally.app import SESSIONS, app
from tiffintally.privacy import Pseudonymizer
from tiffintally.uploads import (
    MAX_UPLOAD_BYTES,
    UploadRejected,
    check_paste_size,
    decode_chat_upload,
    decode_text,
)


class _StubTranscriber:
    def transcribe(self, path, customer_name):
        class R:
            customer = customer_name
            transcribed_text = "kal lunch 1"
            formatted_chat_line = f"- {customer_name}: kal lunch 1"
            backend_used = "stub"
            confidence = 0.5

        return R()


@pytest.fixture
def cook():
    """A fresh browser, so no session cookie leaks between tests."""
    return TestClient(app)


# --- M7: voice-note path traversal --------------------------------------------


def test_voice_note_cannot_escape_its_folder(tmp_path, monkeypatch, cook):
    """`../../x.ogg` used to create data/x.ogg, outside the upload folder."""
    monkeypatch.setattr("tiffintally.app.VoiceNoteTranscriber", _StubTranscriber)

    uploads = tmp_path / "uploads"
    monkeypatch.chdir(tmp_path)
    resp = cook.post(
        "/api/voice-note",
        files={"audio_file": ("../../x.ogg", b"OGGDATA", "audio/ogg")},
        data={"customer_name": "Asha"},
    )
    assert resp.status_code == 200
    # The only file written is inside data/uploads/audio, under a generated name.
    written = [p for p in tmp_path.rglob("*.ogg")]
    assert written, "the note should have been saved"
    for path in written:
        assert "uploads" in path.parts, f"{path} escaped the upload folder"
    assert not (tmp_path / "x.ogg").exists()
    del uploads


def test_voice_note_rejects_an_unlisted_extension(cook):
    resp = cook.post(
        "/api/voice-note",
        files={"audio_file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_voice_note_rejects_an_oversized_file(cook):
    resp = cook.post(
        "/api/voice-note",
        files={"audio_file": ("big.ogg", b"0" * (11 * 1024 * 1024), "audio/ogg")},
    )
    assert resp.status_code == 413


class _StubTranscriber2:
    """Placeholder kept out of the way; see _StubTranscriber above."""


# --- M11: upload limits -------------------------------------------------------


def test_oversized_upload_is_refused():
    with pytest.raises(UploadRejected):
        decode_chat_upload(b"x" * (MAX_UPLOAD_BYTES + 1), "chat.txt")


def test_paste_over_the_cap_is_rejected_with_413(cook):
    resp = cook.post(
        "/process",
        data={"raw_text": "x" * (MAX_UPLOAD_BYTES + 10), "target_date": "tomorrow"},
    )
    assert resp.status_code == 413


def test_check_paste_size_accepts_a_normal_export():
    ok, reason = check_paste_size("12/10/26, 8:00 pm - Asha: kal lunch 1")
    assert ok and reason == ""


def test_utf16_export_is_decoded_not_silently_empty():
    """`errors="replace"` turned a UTF-16 export into an empty prep sheet."""
    text = "12/10/26, 8:00 pm - Asha: kal lunch 1"
    decoded = decode_text(text.encode("utf-16"))
    assert "Asha" in decoded and "kal lunch 1" in decoded


def test_utf16le_without_bom_is_detected():
    text = "12/10/26, 8:00 pm - Asha: kal lunch 1"
    decoded = decode_text(text.encode("utf-16-le"))
    assert "kal lunch 1" in decoded


def test_zip_export_reads_the_chat_member():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "WhatsApp Chat with Asha/chat.txt", "12/10/26, 8:00 pm - Asha: kal lunch 1"
        )
        archive.writestr("WhatsApp Chat with Asha/image.jpg", b"\xff" * 1000)
    decoded = decode_chat_upload(buffer.getvalue(), "export.zip")
    assert "kal lunch 1" in decoded


def test_zip_bomb_is_refused():
    """A member that expands 1000x must not be read into memory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("chat.txt", "A" * 2_000_000)
    with pytest.raises(UploadRejected):
        decode_chat_upload(buffer.getvalue(), "export.zip")


def test_zip_with_no_text_member_is_refused():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("photo.jpg", b"\xff" * 100)
    with pytest.raises(UploadRejected):
        decode_chat_upload(buffer.getvalue(), "export.zip")


# --- M10: what actually leaves the device -------------------------------------


def test_pii_masking_covers_names_phones_and_addresses(tmp_path):
    """The old claim was "names are masked". Only the sender was."""
    p = Pseudonymizer(db_path=tmp_path / "map.db")
    p.register_senders(["Asha Kulkarni", "Priya", "Ravi"])
    text = (
        "roommate Priya ke liye bhi ek, call 98765 43210 or +91-9876543210, "
        "flat 402 Shanti Apts, Asha ka order"
    )
    _sender, masked = p.mask_text("Asha Kulkarni", text)

    assert "Priya" not in masked
    assert "98765 43210" not in masked
    assert "+91-9876543210" not in masked
    assert "402" not in masked
    assert "Shanti Apts" not in masked
    assert "Asha" not in masked


def test_pii_masking_keeps_the_order_intact():
    p = Pseudonymizer(db_path=":memory:")
    p.register_senders(["Asha"])
    _sender, masked = p.mask_text("Asha", "kal lunch 2, Priya ke liye bhi ek")
    assert "kal lunch 2" in masked


def test_sender_token_round_trips():
    p = Pseudonymizer(db_path=":memory:")
    token, _masked = p.mask_text("Asha Kulkarni", "kal lunch 1")
    assert token.startswith("C")
    assert p.depseudonymize(token) == "Asha Kulkarni"


# --- m1: the reminder button must not execute a name --------------------------


def test_reminder_name_cannot_break_out_of_an_onclick(cook):
    """`x');alert(1);//` executed after HTML entity decoding.

    The name may still appear as visible text; what must never happen is it
    becoming part of a JavaScript string literal inside an event handler.
    """
    import re

    hostile = "x');alert(document.cookie);//"
    raw = f"12/10/26, 8:00 pm - {hostile}: kal lunch 1"
    cook.post("/process", data={"raw_text": raw, "target_date": "tomorrow"})
    ledger = cook.get("/ledger")

    handlers = re.findall(r"on\w+\s*=\s*(['\"])(.*?)\1", ledger.text, re.DOTALL)
    assert handlers, "expected at least one inline handler on the page"
    for _quote, body in handlers:
        assert "alert(" not in body, f"injected code reached an event handler: {body!r}"


# --- M11: sessions do not grow without bound ----------------------------------


def test_idle_sessions_are_evicted(monkeypatch):
    monkeypatch.setattr("tiffintally.app.MAX_SESSIONS", 3)
    monkeypatch.setattr("tiffintally.app.SESSION_IDLE_SECONDS", 0)
    for _ in range(6):
        TestClient(app).get("/prep")
    assert len(SESSIONS) <= 4, f"{len(SESSIONS)} sessions retained"


def test_sessions_touch_on_access():
    client = TestClient(app)
    client.get("/prep")
    first = client.cookies.get("tt_sid")
    assert first in SESSIONS
    assert (datetime.now() - SESSIONS[first].touched).total_seconds() < 30


# --- M1: the banner must tell the truth ---------------------------------------


def test_bad_key_marks_every_message_as_fallback(monkeypatch):
    """A page labelled 'gemma-2-9b-it' while the regex did the work."""
    from tiffintally.extract.gemma import GemmaExtractor

    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    monkeypatch.setattr(
        "tiffintally.extract.gemma.GEMMA_API_ENDPOINT",
        "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent",
        raising=False,
    )

    class FakeResponse:
        status_code = 400
        text = "API key not valid"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return FakeResponse()

    monkeypatch.setattr("tiffintally.extract.gemma.httpx.Client", FakeClient)
    monkeypatch.setattr("tiffintally.extract.gemma.time.sleep", lambda *_: None)

    extractor = GemmaExtractor(api_key="definitely-not-valid")
    raw = "12/10/26, 8:00 pm - Asha: kal lunch 2\n12/10/26, 8:01 pm - Ravi: kal dinner 1"
    from tiffintally.parser import parse_chat_export

    batch = extractor.extract_batch_counted(parse_chat_export(raw))
    assert batch.fallback_messages == 2
    assert batch.model_messages == 0
    # A rejected key means no model answered, so no model may be named.
    assert batch.model_name == "rules (regex)"
    assert batch.errors, "the cook should be told the key was rejected"


def test_quota_error_stops_early_instead_of_retrying_every_chunk():
    """One 429 used to cost three attempts per message."""
    from tiffintally.extract.gemma import GemmaExtractor

    calls = {"n": 0}

    class FakeResponse:
        status_code = 429
        text = "quota exceeded"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            calls["n"] += 1
            return FakeResponse()

    monkeypatch = __import__("pytest").MonkeyPatch()
    # The gemini backend, not modal. The Modal backend refuses to run without
    # MODAL_EXTRACTOR_URL and MODAL_EXTRACTOR_TOKEN, so with it pinned here the
    # test never called anything and passed on `calls["n"] == 0` -- a green that
    # proved nothing about retries. This one has to actually reach the 429.
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "a-key-of-plausible-length")
    monkeypatch.setattr("tiffintally.extract.gemma.httpx.Client", FakeClient)
    monkeypatch.setattr("tiffintally.extract.gemma.time.sleep", lambda *_: None)

    class Msg:
        def __init__(self, i):
            self.text = f"kal lunch {i}"
            self.sender = "Asha"
            self.is_system = False
            self.is_media = False
            self.timestamp = datetime(2026, 10, 12, 20, 0)
            self.timestamp_unparsed = False

    try:
        extractor = GemmaExtractor()
        batch = extractor.extract_batch_counted([Msg(i) for i in range(60)])
    finally:
        monkeypatch.undo()

    # 60 messages at 40 per batch is 2 batches; a retry budget must not turn
    # into 60 attempts. The bound is MAX_ATTEMPTS (2) per attempted chunk.
    assert calls["n"] > 0, "the test never reached the endpoint, so it proved nothing"
    assert calls["n"] <= 6, f"{calls['n']} upstream calls for 60 messages"
    assert batch.fallback_messages == 60


# --- late cancels surfaced, not dropped ---------------------------------------


def test_late_cancel_reduction_is_shown_on_the_sheet(cook):
    raw = "12/10/26, 8:00 pm - Asha: kal lunch 2\n12/10/26, 11:15 pm - Asha: kal lunch cancel"
    page = cook.post(
        "/process",
        data={"raw_text": raw, "target_date": "tomorrow", "cutoff": "22:00"},
    )
    assert "Late cancels" in page.text or "late cancel" in page.text.lower()


def test_cook_name_is_never_counted_as_a_customer(cook):
    raw = (
        "12/10/26, 8:00 pm - Asha: kal lunch 2\n"
        "12/10/26, 8:01 pm - Sunita Aunty (cook): ok kal lunch 2 done"
    )
    page = cook.post(
        "/process",
        data={
            "raw_text": raw,
            "target_date": "tomorrow",
            "cook_names": "Sunita Aunty (cook)",
        },
    )
    assert "Sunita Aunty (cook)" not in page.text
