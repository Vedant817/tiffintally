"""Unit tests for WhatsApp voice note transcriber."""

import pytest

from tiffintally.transcribe import VoiceNoteTranscriber


def test_transcribe_offline_fallback(tmp_path):
    dummy_audio = tmp_path / "voice_cancel_note.ogg"
    dummy_audio.write_bytes(b"DUMMY_OGG_HEADER_DATA")

    transcriber = VoiceNoteTranscriber(google_api_key=None)
    result = transcriber.transcribe(
        dummy_audio, customer_name="Rohan", timestamp="14/10/26, 10:15 pm"
    )

    assert result.customer == "Rohan"
    assert result.backend_used == "demo-stub"
    assert "not transcribed" in result.transcribed_text.lower()
    assert "aunty kal lunch cancel" not in result.transcribed_text.lower()
    assert "voice_cancel_note" not in result.transcribed_text.lower()
    from tiffintally.extract.base import heuristic_extract

    events = heuristic_extract(result.transcribed_text, "Rohan")
    assert [(event.action, event.qty) for event in events] == [("none", 0)]
    assert result.confidence == 0.0


def test_transcribe_missing_file():
    transcriber = VoiceNoteTranscriber()
    with pytest.raises(FileNotFoundError):
        transcriber.transcribe("non_existent_audio_file.opus")


def test_transcribe_modification_voice(tmp_path):
    dummy_audio = tmp_path / "customer_jain_request.m4a"
    dummy_audio.write_bytes(b"DUMMY_AUDIO_DATA")

    transcriber = VoiceNoteTranscriber(google_api_key=None)
    result = transcriber.transcribe(dummy_audio, customer_name="Pooja")

    assert result.backend_used == "demo-stub"
    assert "bina pyaaz" not in result.transcribed_text.lower()
    assert result.customer == "Pooja"
