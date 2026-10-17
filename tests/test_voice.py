"""Tests for morning audio brief generator."""

from datetime import datetime

from tiffintally.reconcile import reconcile_orders
from tiffintally.schema import DailyPrepSheet, OrderEvent, SpecialMod
from tiffintally.voice import VoiceBriefService, generate_briefing_script

# Spoken when at least one pending review was already folded into the total.
COUNTED_REVIEW_CLAUSE = (
    "Inme se kuch plates upar ke total mein pehle se shamil hain. "
    "Jo lines count nahi hui, woh is number mein tab tak nahi hain "
    "jab tak aap confirm na kar dein."
)


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
    assert "Namaste!" in script
    assert "Aunty" not in script
    assert "Kal " in script
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
    assert "Namaste!" in res.transcript
    assert "Aunty" not in res.transcript
    assert res.message == "Written summary (no audio, no key configured)"


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


def test_brief_never_says_all_labels_ready_while_orders_await_review():
    """The totals exclude unconfirmed messages, so the wording must say so.

    A headerless paste lands every order in the review queue: the sheet totals 0
    while two real orders wait. Claiming "nothing to cook, all labels ready"
    there is the opposite of the truth, and it is the first thing a cook reads.
    """
    pending = OrderEvent(
        customer="Ravi",
        date="tomorrow",
        meal="lunch",
        qty=2,
        action="new",
        needs_review=True,
        audit_flags=["unparsed_timestamp"],
    )
    sheet = DailyPrepSheet(
        date="Tomorrow",
        total_thalis=0,
        total_lunch=0,
        total_dinner=0,
        unresolved_reviews=[pending],
    )
    script = generate_briefing_script(sheet)

    assert "Sabhi packing labels ready hain" not in script
    assert "1 message(s) abhi aapke check ka intezaar kar rahi hain" in script
    assert "unke bina ka hai" in script, "the cook must know the total excludes them"
    assert "total 0 thalis" in script, "the honest number is still stated"


def test_brief_says_a_packed_review_is_already_in_the_total():
    """An allergy note stays packed and stays in review. The total includes it.

    The flag on this row is the same `unparsed_timestamp` the zero-total test
    uses for a review that was left out. The brief may not infer "excluded"
    from that name. The mark is the one reconcile writes when it applies the row.
    """
    packed = OrderEvent(
        customer="Ravi",
        date="2026-10-19",
        meal="lunch",
        qty=2,
        action="new",
        needs_review=True,
        audit_flags=["unrecognised_request"],
        note="peanut allergy",
        raw_text="Kal lunch 2, bina pyaaz. Peanut allergy please careful.",
        timestamp="2026-10-18 18:01:00",
    )
    sheet = reconcile_orders(
        [packed],
        target_date="2026-10-19",
        as_of=datetime(2026, 10, 18, 18, 0),
    )

    # Replay copies the event before folding it in. The mark lives on the sheet.
    ravi = next(event for event in sheet.unresolved_reviews if event.customer == "Ravi")
    assert ravi.applied_to_plate_count is True
    assert sheet.total_thalis == 2
    assert any("peanut allergy" in label.notes for label in sheet.packing_labels)

    script = generate_briefing_script(sheet)
    assert "Sabhi packing labels ready hain" not in script
    assert "unke bina ka hai" not in script
    assert COUNTED_REVIEW_CLAUSE in script
    assert "total 2 thalis" in script

    # Same flag as the excluded zero-total review. Only the apply mark differs.
    marked = DailyPrepSheet(
        date="Tomorrow",
        total_thalis=2,
        total_lunch=2,
        unresolved_reviews=[
            OrderEvent(
                customer="Ravi",
                date="tomorrow",
                meal="lunch",
                qty=2,
                action="new",
                needs_review=True,
                audit_flags=["unparsed_timestamp"],
                applied_to_plate_count=True,
            )
        ],
    )
    marked_script = generate_briefing_script(marked)
    assert "unke bina ka hai" not in marked_script
    assert COUNTED_REVIEW_CLAUSE in marked_script
    assert "Sabhi packing labels ready hain" not in marked_script


def test_brief_mixed_queue_does_not_exclude_the_packed_review():
    """One packed allergy note and one uncounted line. The total is not 'without both'."""
    packed = OrderEvent(
        customer="Ravi",
        date="2026-10-19",
        meal="lunch",
        qty=2,
        action="new",
        needs_review=True,
        audit_flags=["unrecognised_request"],
        note="peanut allergy",
        raw_text="Kal lunch 2, bina pyaaz. Peanut allergy please careful.",
        timestamp="2026-10-18 18:01:00",
        line_index=0,
    )
    uncounted = OrderEvent(
        customer="Priya",
        date="2026-10-19",
        meal="dinner",
        qty=1,
        action="new",
        needs_review=True,
        audit_flags=["unscoped_decrement"],
        raw_text="Roommate left, cancel one thali from tomorrow.",
        timestamp="2026-10-18 18:02:00",
        line_index=1,
    )
    sheet = reconcile_orders(
        [packed, uncounted],
        target_date="2026-10-19",
        as_of=datetime(2026, 10, 18, 18, 0),
    )

    by_customer = {event.customer: event for event in sheet.unresolved_reviews}
    assert by_customer["Ravi"].applied_to_plate_count is True
    assert by_customer["Priya"].applied_to_plate_count is False
    assert sheet.total_thalis == 2
    assert set(by_customer) >= {"Ravi", "Priya"}
    assert any("peanut allergy" in label.notes for label in sheet.packing_labels)
    assert all(label.customer != "Priya" for label in sheet.packing_labels)

    script = generate_briefing_script(sheet)
    assert "Sabhi packing labels ready hain" not in script
    assert "unke bina ka hai" not in script
    assert COUNTED_REVIEW_CLAUSE in script
    assert "2 message(s) abhi aapke check ka intezaar kar rahi hain" in script
    assert "total 2 thalis" in script


def test_brief_does_not_call_an_applied_cancel_plates_already_in_the_total():
    """A cancel that already changed the count is not a plate sitting inside it.

    The only flag is an unrecognised note, so the row still packs (here: it
    removes the lunch) and stays in review. qty 0 must not flip the
    "plates already included" sentence, even if a caller set the mark.
    """
    order = OrderEvent(
        customer="Ravi",
        date="2026-10-19",
        meal="lunch",
        qty=2,
        action="new",
        raw_text="Kal lunch 2",
        timestamp="2026-10-18 18:00:00",
        line_index=0,
    )
    cancel = OrderEvent(
        customer="Ravi",
        date="2026-10-19",
        meal="lunch",
        qty=0,
        action="cancel",
        needs_review=True,
        audit_flags=["unrecognised_request"],
        note="roommate left",
        raw_text="Roommate left, cancel lunch.",
        timestamp="2026-10-18 18:05:00",
        line_index=1,
    )
    sheet = reconcile_orders(
        [order, cancel],
        target_date="2026-10-19",
        as_of=datetime(2026, 10, 18, 18, 0),
    )

    review_cancel = next(
        event for event in sheet.unresolved_reviews if event.action == "cancel"
    )
    assert review_cancel.applied_to_plate_count is False
    assert sheet.total_thalis == 0
    assert all(label.customer != "Ravi" for label in sheet.packing_labels)

    script = generate_briefing_script(sheet)
    assert COUNTED_REVIEW_CLAUSE not in script
    assert "unke bina ka hai" in script
    assert "Sabhi packing labels ready hain" not in script

    # A hand-built sheet that marks a zero-qty cancel must not use the plate sentence.
    marked_cancel = DailyPrepSheet(
        date="Tomorrow",
        total_thalis=0,
        unresolved_reviews=[
            OrderEvent(
                customer="Ravi",
                date="tomorrow",
                meal="lunch",
                qty=0,
                action="cancel",
                needs_review=True,
                applied_to_plate_count=True,
            )
        ],
    )
    marked_script = generate_briefing_script(marked_cancel)
    assert COUNTED_REVIEW_CLAUSE not in marked_script
    assert "unke bina ka hai" in marked_script


def test_brief_keeps_the_cheerful_closing_when_nothing_is_pending():
    sheet = DailyPrepSheet(
        date="Tomorrow",
        total_thalis=3,
        total_lunch=3,
        total_dinner=0,
    )
    script = generate_briefing_script(sheet)
    assert "Sabhi packing labels ready hain" in script
    assert "intezaar" not in script
