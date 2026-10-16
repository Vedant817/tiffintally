"""
The 12 Bold Tests required by Hacktoberfest 2026 Week 2 Side Hustle.
Directly testing all critical edge cases, privacy, arithmetic hallucination prevention,
and outbound messaging safety.
"""

from datetime import datetime, time
from pathlib import Path

from tiffintally.reconcile import reconcile_ledger, reconcile_orders
from tiffintally.schema import OrderEvent

# The fixtures are the evening of 13 Oct 2026. "tomorrow" is resolved from that clock.
AS_OF = datetime(2026, 10, 13, 12, 0)


# Bold Test 1: Cancel after earlier order -> final count 0, not negative, not 1
def test_bold_1_cancel_after_earlier_order():
    events = [
        OrderEvent(
            customer="Ravi",
            date="tomorrow",
            meal="lunch",
            qty=1,
            action="new",
            timestamp="2026-10-13 18:00:00",
            raw_text="kal lunch 1",
        ),
        OrderEvent(
            customer="Ravi",
            date="tomorrow",
            meal="lunch",
            qty=0,
            action="cancel",
            timestamp="2026-10-13 20:30:00",
            raw_text="kal lunch cancel aunty, team lunch hai",
        ),
    ]
    sheet = reconcile_orders(events, target_date="tomorrow", as_of=AS_OF)
    assert sheet.total_lunch == 0
    assert sheet.total_thalis == 0
    assert len(sheet.packing_labels) == 0
    assert len(sheet.cancellations) == 1
    assert sheet.cancellations[0].customer == "Ravi"


# Bold Test 2: Order arriving AFTER cutoff -> flagged for human approval, not silently applied
def test_bold_2_order_after_cutoff_flagged():
    cutoff = time(22, 0)  # 10:00 PM
    events = [
        OrderEvent(
            customer="Deepak",
            date="tomorrow",
            meal="lunch",
            qty=2,
            action="new",
            timestamp="2026-10-13 22:30:00",
            raw_text="aunty kal lunch 2 add karo please late ho gaya",
        )
    ]
    sheet = reconcile_orders(events, target_date="tomorrow", cutoff_time=cutoff, as_of=AS_OF)
    assert sheet.total_lunch == 0
    assert sheet.total_thalis == 0
    assert len(sheet.late_orders) == 1
    assert sheet.late_orders[0].customer == "Deepak"
    assert sheet.late_orders[0].is_late is True


# Bold Test 3: Secondary customer named ("Priya ke liye bhi ek lunch add kar dena")
def test_bold_3_secondary_customer_splitting():
    events = [
        OrderEvent(
            customer="Karan",
            secondary_customer="Priya",
            date="tomorrow",
            meal="lunch",
            qty=2,
            action="new",
            timestamp="2026-10-13 19:00:00",
            raw_text="Kal lunch 1 plate. Aur meri roommate Priya ke liye bhi ek lunch add kar dena",
        )
    ]
    sheet = reconcile_orders(events, target_date="tomorrow", as_of=AS_OF)
    assert sheet.total_lunch == 2
    assert len(sheet.packing_labels) == 2
    customers = {p.customer: p.qty for p in sheet.packing_labels}
    assert customers.get("Karan") == 1
    assert customers.get("Priya") == 1


# Bold Test 4: Standing order paused on "Sunday off"
def test_bold_4_standing_order_paused():
    standing = {"Ravi": 1, "Amit": 1}
    events = [
        OrderEvent(
            customer="Ravi",
            date="Sunday",
            meal="both",
            qty=0,
            action="pause",
            timestamp="2026-10-13 20:00:00",
            raw_text="going home for weekend, Sunday off",
        )
    ]
    sheet = reconcile_orders(events, target_date="Sunday", standing_orders=standing, as_of=AS_OF)
    # Ravi paused -> 0; Amit remains -> 1
    assert sheet.total_lunch == 1
    labels = {lbl.customer: lbl.qty for lbl in sheet.packing_labels}
    assert "Ravi" not in labels
    assert labels.get("Amit") == 1


# Bold Test 5: Pure chit-chat ("thank you aunty, khana mast tha") -> zero orders
def test_bold_5_pure_chitchat_yields_zero_orders():
    events = [
        OrderEvent(
            customer="Sneha",
            date="today",
            meal="unspecified",
            qty=0,
            action="none",
            timestamp="2026-10-13 14:00:00",
            raw_text="thank you aunty, khana mast tha! Bahut swadisht paneer tha.",
        )
    ]
    sheet = reconcile_orders(events, target_date="tomorrow")
    assert sheet.total_thalis == 0
    assert len(sheet.packing_labels) == 0


# Bold Test 6: Devanagari script order ("कल दो थाली दोपहर को भेजना") -> lunch qty=2
def test_bold_6_devanagari_order_parsing():
    from tiffintally.extract.base import heuristic_extract

    text = "कल दो थाली दोपहर को भेजना, बिना प्याज के"
    events = heuristic_extract(text, sender="Pooja")
    assert len(events) >= 1
    ev = events[0]
    assert ev.qty == 2
    assert ev.meal == "lunch"
    assert ev.action == "new"
    assert "no onion" in ev.mods or "bina pyaaz" in ev.mods


# Bold Test 7: Payment note ("500 GPay kiya aunty") -> updates ledger, zero plates added
def test_bold_7_payment_note_ledger_update():
    events = [
        OrderEvent(
            customer="Vikram",
            date="today",
            meal="unspecified",
            qty=0,
            action="payment",
            payment_amount=500.0,
            timestamp="2026-10-13 16:00:00",
            raw_text="₹500 GPay kiya aunty check kar lo",
        )
    ]
    # Check kitchen cooking sheet: 0 plates
    sheet = reconcile_orders(events, target_date="tomorrow")
    assert sheet.total_thalis == 0

    # Check ledger: records 500 paid, reduces balance
    previous_balances = {"vikram": 1200.0}
    ledger = reconcile_ledger(events, price_per_thali=80.0, previous_balances=previous_balances)
    assert ledger["vikram"].total_paid == 500.0
    assert ledger["vikram"].balance_due == 700.0


# Bold Test 8: Duplicate forwarded message -> counted once, not twice
def test_bold_8_duplicate_forwarded_message():
    dup_text = "kal lunch 2 plates"
    events = [
        OrderEvent(
            customer="Ravi",
            date="tomorrow",
            meal="lunch",
            qty=2,
            action="new",
            timestamp="2026-10-13 21:00:00",
            raw_text=dup_text,
        ),
        OrderEvent(
            customer="Ravi",
            date="tomorrow",
            meal="lunch",
            qty=2,
            action="new",
            timestamp="2026-10-13 21:00:00",
            raw_text=dup_text,
        ),
    ]
    sheet = reconcile_orders(events, target_date="tomorrow", as_of=AS_OF)
    assert sheet.total_lunch == 2
    assert sheet.total_thalis == 2
    assert len(sheet.packing_labels) == 1


# Bold Test 9: Malformed JSON from model -> fallback, routed to review queue
def test_bold_9_malformed_json_fallback_and_review():
    from tiffintally.extract.base import parse_and_validate_llm_json

    bad_json = "{ 'action': 'new', 'qty': 2, 'unclosed_json: ..."
    events, err = parse_and_validate_llm_json(bad_json, raw_text="lunch do please", sender="Aman")
    assert len(events) >= 1
    assert events[0].confidence < 0.70  # Low confidence triggers review
    sheet = reconcile_orders(events, target_date="tomorrow")
    assert len(sheet.unresolved_reviews) >= 1


# Bold Test 10: Missing GEMMA_API_KEY -> informative error, graceful fallback
def test_bold_10_missing_api_key_graceful_fallback(monkeypatch):
    """With no endpoint and no key, the regex answers and says so.

    The model used to require a Google AI Studio key. It is served on Modal now,
    so "no key" is no longer the offline signal; "no endpoint" is.
    """
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "off")

    from tiffintally.extract.gemma import GemmaExtractor

    extractor = GemmaExtractor(api_key=None)
    assert extractor.is_available() is False

    res = extractor.extract_from_text("kal lunch 1 plate", sender="Rohit")
    assert res.used_fallback is True
    # Not "<model>-fallback". Naming the configured model and bolting a suffix
    # on it is what let a sheet read "gemma-4-26b-a4b-it-fallback" while Gemma
    # had never been called. The label now names the thing that actually ran.
    assert res.model_name == "rules (regex)"
    assert len(res.events) >= 1
    assert res.events[0].qty == 1
    assert res.events[0].meal == "lunch"


def test_bold_10b_gemini_backend_still_needs_a_key(monkeypatch):
    """The AI Studio path still refuses to run without a key."""
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "gemini")
    from tiffintally.extract.gemma import GemmaExtractor

    assert GemmaExtractor(api_key=None).is_available() is False
    assert GemmaExtractor(api_key="not-a-real-key").is_available() is True


# Bold Test 11: Secret scan across entire repo -> zero live keys, git diff clean
def test_bold_11_secret_scan():
    repo_root = Path(__file__).parent.parent
    banned_substrings = [
        "AIzaSy",  # Google API key prefix
        "sk-ant-",  # Anthropic prefix
        "xai-",  # xAI prefix
    ]

    for p in repo_root.glob("**/*"):
        if p.is_file():
            # Exclude git directory, test scanner file itself, and binary files
            if (
                ".git" in p.parts
                or ".venv" in p.parts
                or p.name == "test_bold.py"
                or p.suffix in [".pyc", ".db", ".png", ".jpg", ".mp3"]
            ):
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            for banned in banned_substrings:
                assert banned not in text, f"Potential live secret found in {p}"


# Bold Test 12: Zero pywhatkit or outbound messaging calls anywhere in source
def test_bold_12_no_messaging_or_sms_send():
    repo_root = Path(__file__).parent.parent
    banned_terms = [
        "pywhatkit",
        "twilio.rest",
        "messages.create",
        "api.whatsapp.com/send",
        "graph.facebook.com",
    ]

    for file_path in (repo_root / "tiffintally").glob("**/*.py"):
        content = file_path.read_text(encoding="utf-8")
        for banned in banned_terms:
            assert banned not in content, f"Banned messaging call '{banned}' found in {file_path}"
