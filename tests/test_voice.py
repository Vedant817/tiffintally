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

    # Pre-create cached dummy audio file
    fake_audio = tmp_path / "brief_Tomorrow.mp3"
    fake_audio.write_bytes(b"FAKE_MP3_DATA")

    service = VoiceBriefService(api_key=None)
    sheet = DailyPrepSheet(date="Tomorrow", total_thalis=12, total_lunch=12)
    res = service.generate_morning_brief(sheet, force_refresh=False)

    assert res.audio_path == str(fake_audio)
    assert res.used_tts_api is True
    assert "cache" in res.message.lower()
