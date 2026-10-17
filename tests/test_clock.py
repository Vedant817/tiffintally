"""The sheet clock is India time even when the process clock is UTC."""

from datetime import datetime

from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.parser import parse_chat_export
from tiffintally.reconcile import reconcile_orders


def test_morning_ist_sheet_keeps_last_nights_tomorrow(monkeypatch):
    """9:05 pm on 17 Oct saying kal lunch 2, sheet built at 03:00 IST on 18 Oct.

    target today must total 2. The same sheet built from a UTC clock at 21:30
    on 17 Oct (which is 03:00 IST) totals 0, because "today" is still the 17th.
    """
    monkeypatch.setattr("tiffintally.extract.gemma.EXTRACTOR_BACKEND", "off")
    messages = parse_chat_export("17/10/26, 9:05 pm - Ravi: kal lunch 2")
    events = GemmaExtractor().extract_batch_counted(messages).events

    monkeypatch.setattr("tiffintally.reconcile.kitchen_now", lambda: datetime(2026, 10, 18, 3, 0))
    ist = reconcile_orders(events, target_date="today")
    assert ist.date == "2026-10-18"
    assert ist.total_thalis == 2

    monkeypatch.setattr("tiffintally.reconcile.kitchen_now", lambda: datetime(2026, 10, 17, 21, 30))
    utc = reconcile_orders(events, target_date="today")
    assert utc.date == "2026-10-17"
    assert utc.total_thalis == 0
