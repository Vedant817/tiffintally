"""
ElevenLabs Morning Kitchen Audio Briefing Generator.
Transforms DailyPrepSheet into a warm, natural Hinglish spoken morning summary for the cook.
Caches generated MP3s locally and provides instant text fallback when unkeyed or offline.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from tiffintally.schema import DailyPrepSheet

DEFAULT_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"
)  # Rachel / default warm voice
BRIEFINGS_DIR = Path("data/briefings")


class VoiceBriefResult(BaseModel):
    audio_path: Optional[str] = None
    transcript: str
    character_count: int
    used_tts_api: bool
    voice_id: str
    message: str


def generate_briefing_script(sheet: DailyPrepSheet) -> str:
    """Generate a warm, natural conversational Hinglish morning briefing for the kitchen cook."""
    parts = []
    parts.append(
        f"Namaste Aunty! Aaj {sheet.date} ke liye total {sheet.total_thalis} thalis pack karni hain."
    )
    if sheet.total_lunch > 0:
        parts.append(f"Lunch ke {sheet.total_lunch} orders hain.")
    if sheet.total_dinner > 0:
        parts.append(f"Raat ke dinner ke {sheet.total_dinner} orders hain.")

    if sheet.special_mods:
        mod_texts = [f"{m.customer} ka {m.mod_description}" for m in sheet.special_mods[:4]]
        parts.append(f"Khaas dhyan: {', '.join(mod_texts)}.")

    if sheet.cancellations:
        cancels = [c.customer for c in sheet.cancellations[:3]]
        parts.append(f"Cancellations note kar lijiye: {', '.join(cancels)}.")

    if sheet.late_orders:
        parts.append(
            f"{len(sheet.late_orders)} late messages aaye hain jinhe aap review screen par check kar sakti hain."
        )

    # A message the cook has not confirmed yet is deliberately left out of the
    # totals. Saying "nothing to cook" and "all labels ready" while orders are
    # sitting in the review queue tells the cook the opposite of the truth, so
    # name the pending count instead.
    pending = len(sheet.unresolved_reviews) + len(sheet.late_orders)
    if pending:
        parts.append(
            f"{pending} message(s) abhi aapke check ka intezaar kar rahi hain, isliye upar ka total "
            "unke bina ka hai. Review screen par confirm kar dein."
        )
        parts.append("Confirm hone ke baad ke labels hi ready hain. Shubh prabhat!")
    else:
        parts.append("Sabhi packing labels ready hain. Shubh prabhat aur din accha rahe!")
    return " ".join(parts)


def sheet_fingerprint(sheet: DailyPrepSheet) -> str:
    """Stable digest of what the brief actually says.

    The cache used to be keyed by date alone, so cook B heard cook A's plate
    counts for the same day, and a late cancel did not change the audio at all.
    """
    payload = json.dumps(
        {
            "date": sheet.date,
            "lunch": sheet.total_lunch,
            "dinner": sheet.total_dinner,
            "mods": [m.model_dump() for m in sheet.special_mods],
            "cancels": [c.customer for c in sheet.cancellations],
            "late": len(sheet.late_orders),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class VoiceBriefService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        session_id: str = "shared",
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or DEFAULT_VOICE_ID
        self.session_id = session_id
        BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def generate_morning_brief(
        self, sheet: DailyPrepSheet, force_refresh: bool = False
    ) -> VoiceBriefResult:
        transcript = generate_briefing_script(sheet)
        char_count = len(transcript)

        safe_session = "".join(c for c in self.session_id if c.isalnum())[:16] or "shared"
        safe_date = sheet.date.replace(":", "-").replace(" ", "_")
        cache_file = BRIEFINGS_DIR / (
            f"brief_{safe_session}_{safe_date}_{sheet_fingerprint(sheet)}.mp3"
        )

        if cache_file.exists() and not force_refresh:
            return VoiceBriefResult(
                audio_path=str(cache_file),
                transcript=transcript,
                character_count=char_count,
                used_tts_api=True,
                voice_id=self.voice_id,
                message="Loaded from local audio cache",
            )

        if not self.is_available():
            return VoiceBriefResult(
                audio_path=None,
                transcript=transcript,
                character_count=char_count,
                used_tts_api=False,
                voice_id=self.voice_id,
                message="ElevenLabs API key not set; fallback text transcript available",
            )

        # Call ElevenLabs API
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": transcript,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    with open(cache_file, "wb") as f:
                        f.write(resp.content)
                    return VoiceBriefResult(
                        audio_path=str(cache_file),
                        transcript=transcript,
                        character_count=char_count,
                        used_tts_api=True,
                        voice_id=self.voice_id,
                        message=f"Successfully generated {char_count} characters with ElevenLabs",
                    )
                else:
                    return VoiceBriefResult(
                        audio_path=None,
                        transcript=transcript,
                        character_count=char_count,
                        used_tts_api=False,
                        voice_id=self.voice_id,
                        message=f"ElevenLabs HTTP {resp.status_code}: {resp.text[:100]}",
                    )
        except Exception as e:
            return VoiceBriefResult(
                audio_path=None,
                transcript=transcript,
                character_count=char_count,
                used_tts_api=False,
                voice_id=self.voice_id,
                message=f"TTS error: {e}",
            )
