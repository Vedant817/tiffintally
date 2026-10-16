"""Parser hardening checks for the served model output.

The adapter emits `["customer": ...]` where `{` belongs. One malformed bracket
used to invalidate the whole reply, so a single bad event threw away every other
event in the same message.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from modal_serve import _normalise_brackets, _parse  # noqa: E402

MALFORMED = (
    '{"events": [{"customer": "C001", "date": "kal", "meal": "lunch", '
    '"qty": "2", "mods": "", "action": "order"}], '
    '["customer": "C001", "date": "kal", "meal": "dinner", '
    '"qty": "0", "mods": "", "action": "cancel"}] }'
)

CLEAN = (
    '{"events": [{"customer": "C001", "date": "kal", "meal": "lunch", '
    '"qty": 2, "mods": ["no onion"], "action": "new"}]}'
)


def test_malformed_bracket_yields_both_events():
    events, repaired = _parse(MALFORMED)
    assert repaired == 1, "the repair must be reported, not hidden"
    assert len(events) == 2, events
    assert events[0]["meal"] == "lunch"
    assert events[0]["qty"] == 2
    assert events[1]["meal"] == "dinner"
    assert events[1]["action"] == "cancel"


def test_clean_output_is_untouched():
    events, repaired = _parse(CLEAN)
    assert repaired == 0
    assert events[0]["mods"] == ["no onion"]
    assert events[0]["qty"] == 2


def test_string_quantity_is_coerced():
    events, _ = _parse(
        '{"events": [{"customer": "C001", "meal": "lunch", "qty": "3", '
        '"mods": "", "action": "new"}]}'
    )
    assert events[0]["qty"] == 3


def test_real_arrays_are_not_rewritten():
    """`"mods": ["no onion"]` has no colon, so it must stay an array."""
    out = _normalise_brackets(CLEAN)
    assert '"mods": ["no onion"]' in out


def test_garbage_returns_no_events():
    events, _ = _parse("I could not help with that request.")
    assert events == []


def test_truncated_output_keeps_the_complete_event():
    truncated = (
        '{"events": [{"customer": "C001", "meal": "lunch", "qty": 1, '
        '"mods": [], "action": "new"}, {"customer": "C001", "meal": "din'
    )
    events, _ = _parse(truncated)
    assert len(events) == 1
    assert events[0]["qty"] == 1


def test_unknown_action_and_meal_are_invalid_not_default_orders():
    events, _ = _parse(
        '{"events": [{"customer": "C001", "meal": "brunch", "qty": 1, '
        '"mods": [], "action": "order"}]}'
    )
    assert events[0]["invalid"] is True
    assert set(events[0]["invalid_reasons"]) == {"invalid_action", "invalid_meal"}
