"""Unit tests for WhatsApp chat export parsing."""

from pathlib import Path

from tiffintally.parser import (
    clean_text,
    is_media_message,
    is_system_notification,
    parse_chat_export,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_android_export_parsing():
    content = (FIXTURES_DIR / "android_export.txt").read_text(encoding="utf-8")
    messages = parse_chat_export(content)

    assert len(messages) >= 5

    # Check system message
    assert messages[0].is_system is True
    assert "encrypted" in messages[0].text.lower()

    # Check first actual customer order
    m1 = messages[1]
    assert m1.sender == "Ravi"
    assert m1.text == "kal lunch 2, dinner skip"
    assert m1.is_media is False
    assert m1.is_system is False

    # Check multiline message
    m2 = messages[2]
    assert m2.sender == "Priya"
    assert "aaj roti nahi rice" in m2.text
    assert "Please make it less spicy" in m2.text
    assert "Thanks aunty!" in m2.text

    # Check media omitted
    m3 = messages[3]
    assert m3.sender == "Vikram"
    assert m3.is_media is True

    # Check phone number sender
    m4 = messages[4]
    assert "+91 98765 43210" in m4.sender
    assert "₹1500 GPay kiya" in m4.text


def test_ios_export_parsing():
    content = (FIXTURES_DIR / "ios_export.txt").read_text(encoding="utf-8")
    messages = parse_chat_export(content)

    assert len(messages) == 5

    # System message
    assert messages[0].is_system is True

    # iOS 12h message
    m1 = messages[1]
    assert m1.sender == "Ravi"
    assert m1.text == "kal lunch 2, dinner skip"

    # Multiline
    m2 = messages[2]
    assert m2.sender == "Priya"
    assert "Line two of message" in m2.text

    # Media omitted
    m3 = messages[3]
    assert m3.sender == "Vikram"
    assert m3.is_media is True

    # iOS 24h message
    m4 = messages[4]
    assert m4.sender == "Rohan"
    assert "2 plates dinner today" in m4.text


def test_raw_text_paste_without_headers():
    raw = "Kal lunch 2 plates bhejo\nNo spicy please"
    messages = parse_chat_export(raw)
    assert len(messages) == 1
    assert "Kal lunch 2 plates bhejo" in messages[0].text
    assert "No spicy please" in messages[0].text


def test_unicode_cleaning():
    text_with_marks = "\u200eRavi:\u202fkal lunch\xa02"
    cleaned = clean_text(text_with_marks)
    assert cleaned == "Ravi: kal lunch 2"


def test_media_detection():
    assert is_media_message("<Media omitted>") is True
    assert is_media_message("‎image omitted") is True
    assert is_media_message("photo omitted") is False  # not in standard list
    assert is_media_message("Kal lunch 2") is False


def test_system_notification_detection():
    assert is_system_notification("Messages and calls are end-to-end encrypted.") is True
    assert is_system_notification("Ravi left the group") is True
    assert is_system_notification("Kal lunch bhejo") is False
    assert is_system_notification("kal 1 lunch, mera roommate left for home") is False


def test_dot_and_iso_headers_are_separate_messages():
    content = (
        "13.10.26, 22:17 - Neha: kal 1 lunch, mera roommate left for home\n"
        "2026-10-13 22:18 - Amit: aaj raat 1 dinner\n"
    )
    messages = parse_chat_export(content)
    assert len(messages) == 2
    assert messages[0].sender == "Neha"
    assert messages[0].is_system is False
    assert "roommate left" in messages[0].text
    assert messages[0].timestamp.day == 13
    assert messages[0].timestamp_unparsed is False
    assert messages[1].sender == "Amit"
    assert "aaj raat" in messages[1].text
    assert messages[1].timestamp.hour == 22


def test_unparsed_header_is_flagged():
    content = "32/13/26, 22:17 - Neha: kal lunch 1\n"
    messages = parse_chat_export(content)
    assert len(messages) == 1
    assert messages[0].timestamp_unparsed is True
    assert messages[0].sender == "Neha"
