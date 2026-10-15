"""Tests for morning audio brief generator."""

from tiffintally.schema import DailyPrepSheet, OrderEvent, SpecialMod
from tiffintally.voice import VoiceBriefService, generate_briefing_script


def test_generate_briefing_script():
    sheet = DailyPrepSheet(
        date="Tomorrow",
        total_thalis=45,
        total_lunch=35,
        total_dinner=10,
        special_mods=[
            SpecialMod(customer="Priya", meal="lunch", mod_description="roti nahi rice"),
            SpecialMod(customer="Amit", meal="lunch", mod_description="less spicy"),
        ],
        cancellations=[
            OrderEvent(customer="Sneha", date="tomorrow", meal="lunch", qty=0, action="cancel")
        ],
    )
    script = generate_briefing_script(sheet)
    assert "Namaste Aunty!" in script
    assert "total 45 thalis" in script
    assert "Lunch ke 35 orders" in script
    assert "Priya ka roti nahi rice" in script
    assert "Sneha" in script


def test_voice_brief_service_fallback_without_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    service = VoiceBriefService(api_key=None)
    assert service.is_available() is False

    sheet = DailyPrepSheet(date="Tomorrow", total_thalis=10, total_lunch=10)
    res = service.generate_morning_brief(sheet)

    assert res.audio_path is None
    assert res.used_tts_api is False
    assert res.character_count > 0
    assert "Namaste Aunty" in res.transcript


def test_voice_brief_caching(tmp_path, monkeypatch):
    import tiffintally.voice as voice_module

    monkeypatch.setattr(voice_module, "BRIEFINGS_DIR", tmp_path)

    sheet = DailyPrepSheet(date="Tomorrow", total_thalis=12, total_lunch=12)
    fingerprint = voice_module.sheet_fingerprint(sheet)
    fake_audio = tmp_path / f"brief_cookA1_Tomorrow_{fingerprint}.mp3"
    fake_audio.write_bytes(b"FAKE_MP3_DATA")

    service = VoiceBriefService(api_key=None, session_id="cookA1")
    res = service.generate_morning_brief(sheet, force_refresh=False)

    assert res.audio_path == str(fake_audio)
    assert res.used_tts_api is True
    assert "cache" in res.message.lower()


def test_voice_cache_does_not_cross_cooks(tmp_path, monkeypatch):
    """Cook B must not hear cook A's plate counts for the same day."""
    import tiffintally.voice as voice_module

    monkeypatch.setattr(voice_module, "BRIEFINGS_DIR", tmp_path)

    cook_a_sheet = DailyPrepSheet(date="Tomorrow", total_thalis=12, total_lunch=12)
    cook_b_sheet = DailyPrepSheet(date="Tomorrow", total_thalis=3, total_lunch=3)

    assert voice_module.sheet_fingerprint(cook_a_sheet) != voice_module.sheet_fingerprint(
        cook_b_sheet
    )

    audio = tmp_path / f"brief_cookA1_Tomorrow_{voice_module.sheet_fingerprint(cook_a_sheet)}.mp3"
    audio.write_bytes(b"COOK A AUDIO")

    result = VoiceBriefService(api_key=None, session_id="cookB2").generate_morning_brief(
        cook_b_sheet
    )
    assert result.audio_path is None, "cook B was served cook A's cached audio"


def test_voice_cache_refreshes_after_a_late_cancel(tmp_path, monkeypatch):
    """A re-run after a late cancel must not replay yesterday's counts."""
    import tiffintally.voice as voice_module

    monkeypatch.setattr(voice_module, "BRIEFINGS_DIR", tmp_path)

    before = DailyPrepSheet(date="Tomorrow", total_thalis=12, total_lunch=12)
    after = DailyPrepSheet(date="Tomorrow", total_thalis=10, total_lunch=10)

    assert voice_module.sheet_fingerprint(before) != voice_module.sheet_fingerprint(after)
