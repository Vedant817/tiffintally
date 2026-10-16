"""Rules parser coverage for the eight misses in modal run 31."""

import pytest

from tiffintally.extract.base import heuristic_extract


def test_pause_range_is_not_a_single_sunday():
    events = heuristic_extract(
        "going home for Diwali, Sunday se next Thursday tak band rakhna",
        "Ananya",
    )
    assert len(events) == 1
    assert events[0].action == "pause"
    assert events[0].date == "sunday"
    assert events[0].pause_until == "thursday"
    assert events[0].needs_review is True
    assert "date_range" in events[0].audit_flags


def test_gujarati_lunch_does_not_invent_a_mod():
    events = heuristic_extract("shaak rotli 2 dabba please lunch", "Meera")
    assert len(events) == 1
    assert events[0].meal == "lunch"
    assert events[0].qty == 2
    assert events[0].mods == []


@pytest.mark.xfail(strict=True, reason="T4-002 intentionally removed test-fitted dietary literals")
def test_curd_swap_keeps_both_mods():
    events = heuristic_extract("1 thali lunch, replace curd with extra sabzi", "Ravi")
    assert events[0].meal == "lunch"
    assert events[0].qty == 1
    assert events[0].mods == ["no curd", "extra sabzi"]


def test_typo_dinner_cancel_is_tomorrow():
    events = heuristic_extract("tomrw dinr cncl", "Priya")
    assert len(events) == 1
    assert events[0].date == "tomorrow"
    assert events[0].meal == "dinner"
    assert events[0].action == "cancel"
    assert events[0].qty == 0


@pytest.mark.xfail(strict=True, reason="T4-002 intentionally removed test-fitted dietary literal")
def test_typo_less_spicy():
    events = heuristic_extract("dinr 1 no spic", "Karan")
    assert events[0].meal == "dinner"
    assert events[0].qty == 1
    assert events[0].action == "new"
    assert events[0].mods == ["less spicy"]


def test_lunch_and_dinner_stay_separate():
    events = heuristic_extract("do lunch aur ek dinner", "Amit")
    assert [(e.meal, e.qty, e.action) for e in events] == [
        ("lunch", 2, "new"),
        ("dinner", 1, "new"),
    ]


@pytest.mark.xfail(strict=True, reason="T4-002 intentionally removed test-fitted dietary literal")
def test_kadak_roti_stays_one_mod():
    events = heuristic_extract("aunty ekdum kadak roti bhejna 1 thali dinner", "Pooja")
    assert events[0].meal == "dinner"
    assert events[0].mods == ["kadak roti"]


@pytest.mark.xfail(strict=True, reason="T4-002 intentionally removed test-fitted dietary literal")
def test_gujarati_extra_roti():
    events = heuristic_extract("rotli vadhare aapjo ek thali sathe", "Sneha")
    assert events[0].mods == ["extra roti"]
    assert events[0].qty == 1


def test_not_going_home_is_an_order():
    events = heuristic_extract("not going home, 2 lunch tomorrow please", "Meera")
    assert len(events) == 1
    assert events[0].action == "new"
    assert events[0].meal == "lunch"
    assert events[0].qty == 2
    assert events[0].date == "tomorrow"


def test_kadak_chai_is_not_kadak_roti():
    events = heuristic_extract("kadak chai ke sath 1 lunch", "Ravi")
    assert events[0].mods == []
    assert events[0].meal == "lunch"
    assert events[0].qty == 1


def test_shaak_vadhare_is_not_extra_roti():
    events = heuristic_extract("shaak vadhare ek thali lunch", "Meera")
    assert events[0].mods == []


def test_each_meal_keeps_its_own_quantity():
    events = heuristic_extract("kal lunch 2, dinner 1", "Amit")
    assert [(e.meal, e.qty, e.action) for e in events] == [
        ("lunch", 2, "new"),
        ("dinner", 1, "new"),
    ]
    events = heuristic_extract("do dinner please", "Amit")
    assert events[0].meal == "dinner"
    assert events[0].qty == 2


def test_skip_binds_to_the_nearest_meal():
    events = heuristic_extract("lunch skip dinner 1", "Ravi")
    assert [(e.meal, e.qty, e.action) for e in events] == [
        ("lunch", 0, "cancel"),
        ("dinner", 1, "new"),
    ]
    events = heuristic_extract("kal lunch 2, dinner skip", "Ravi")
    assert [(e.meal, e.qty, e.action) for e in events] == [
        ("lunch", 2, "new"),
        ("dinner", 0, "cancel"),
    ]


def test_nahi_chahiye_cancels_instead_of_changing():
    events = heuristic_extract("2 lunch nahi chahiye", "Ravi")
    assert events[0].action == "cancel"
    assert events[0].meal == "lunch"
    assert events[0].qty == 0


def test_payment_amount_survives_via_and_done():
    via = heuristic_extract("paid 1500 via PhonePe for this week", "Ravi")
    assert via[0].action == "payment"
    assert via[0].payment_amount == 1500.0
    assert via[0].qty == 0
    done = heuristic_extract("GPay done 1500", "Ravi")
    assert done[0].action == "payment"
    assert done[0].payment_amount == 1500.0
    classic = heuristic_extract("500 gpay kiya", "Ravi")
    assert classic[0].payment_amount == 500.0
    order = heuristic_extract("2 thali lunch", "Guest")
    assert order[0].action == "new"


def test_bhi_ek_keeps_the_sender_plate():
    events = heuristic_extract(
        "Kal lunch 1 plate. Aur meri roommate Tanvi ke liye bhi ek lunch add kar dena",
        "Karan",
    )
    assert len(events) == 1
    assert events[0].qty == 2
    assert events[0].secondary_customer == "Tanvi"
