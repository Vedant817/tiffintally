"""Tests for the scorer demo, its metrics, and its hand-written repair rules.

These tests pin behaviour that would otherwise be tempting to "improve":
the lab never calls a model, and the adversarial suite does not pass.
"""

import pytest
from fastapi.testclient import TestClient

from tiffintally.app import app
from tiffintally.benchmarks import (
    STANDARD_BENCHMARK_SUITES,
    auto_repair_events,
    compute_extraction_metrics,
    evaluate_and_heal_loop,
)


@pytest.fixture
def client():
    return TestClient(app)


def _suite(suite_id):
    return next(suite for suite in STANDARD_BENCHMARK_SUITES if suite["id"] == suite_id)


def test_compute_extraction_metrics_exact_match():
    gold = [
        {
            "customer": "Rohan",
            "meal": "lunch",
            "qty": 2,
            "items": ["thali"],
            "mods": ["no onion"],
            "action": "new",
            "secondary_customer": None,
        }
    ]
    pred = [dict(gold[0])]
    metrics, flaws = compute_extraction_metrics(pred, gold, "lunch 2 bina pyaaz")

    assert metrics.f1_score == 1.0
    assert metrics.strict_accuracy == 1.0
    assert metrics.lenient_accuracy == 1.0
    assert metrics.composite_score == 100.0
    assert not flaws


def test_auto_repair_negated_cancellation():
    flawed_pred = [
        {
            "customer": "Ravi",
            "meal": "lunch",
            "qty": 0,
            "action": "cancel",
            "mods": [],
        }
    ]
    raw_text = "kal lunch cancel mat karna, 2 hi chahiye please"
    diagnosed_flaws = ["ACTION_MISMATCH: Intent action incorrect"]

    repaired, actions = auto_repair_events(flawed_pred, raw_text, diagnosed_flaws, attempt=1)
    assert repaired[0]["action"] == "new"
    assert any("negated cancellation" in act.lower() for act in actions)


def test_auto_repair_dietary_constraints():
    flawed_pred = [
        {
            "customer": "Priya",
            "meal": "lunch",
            "qty": 1,
            "action": "new",
            "mods": [],
        }
    ]
    raw_text = "kal lunch 1 thali, bina pyaaz, kam mirchi aur roti nahi rice"
    diagnosed_flaws = ["MODS_MISMATCH: Missing dietary modifications"]

    repaired, actions = auto_repair_events(flawed_pred, raw_text, diagnosed_flaws, attempt=1)
    mods = repaired[0]["mods"]
    assert "no onion" in mods
    assert "less spicy" in mods
    assert "roti nahi rice" in mods


def test_evaluate_and_heal_retry_loop_passes_threshold():
    gold = {
        "customer": "Priya",
        "meal": "lunch",
        "qty": 1,
        "action": "new",
        "mods": ["less spicy", "no onion", "roti nahi rice"],
        "items": ["thali"],
        "secondary_customer": None,
    }
    # Initial flawed response from model
    flawed_pred = [
        {
            "customer": "Priya",
            "meal": "lunch",
            "qty": 1,
            "action": "new",
            "mods": [],
        }
    ]
    raw_text = "kal lunch 1 thali, bina pyaaz, kam mirchi aur roti nahi rice please"

    record = evaluate_and_heal_loop(
        raw_text=raw_text,
        gold_event=gold,
        initial_prediction=flawed_pred,
        threshold=90.0,
        max_retries=5,
    )

    assert record.passed is True
    assert record.final_score >= 90.0
    assert record.total_retries >= 2
    assert record.iterations[0].metrics.composite_score < 90.0
    assert record.iterations[-1].metrics.composite_score >= 90.0


def test_benchmarks_routes(client):
    # Test GET /benchmarks
    res = client.get("/benchmarks")
    assert res.status_code == 200
    assert "Scorer Demo With Repair Rules" in res.text

    # Test GET /api/benchmarks/suites
    suites_res = client.get("/api/benchmarks/suites")
    assert suites_res.status_code == 200
    suites_data = suites_res.json()
    assert len(suites_data) == len(STANDARD_BENCHMARK_SUITES)

    # Test POST /api/benchmarks/run
    run_res = client.post(
        "/api/benchmarks/run",
        data={
            "suite_id": "suite_negation_intent",
            "threshold": "85.0",
            "max_retries": "3",
            "inject_flaw": "true",
        },
    )
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["passed"] is True
    assert data["final_score"] >= 85.0
    assert "iterations" in data
    assert len(data["iterations"]) >= 1


# --- what this page must not be taken for -------------------------------------


def test_lab_without_an_initial_prediction_makes_no_network_call(monkeypatch):
    """The lab starts from the offline rules. It never sends anything anywhere."""
    import httpx

    def forbidden(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("the scorer demo must not make an HTTP call")

    monkeypatch.setattr(httpx, "post", forbidden)
    monkeypatch.setattr(httpx.Client, "post", forbidden)

    for suite in STANDARD_BENCHMARK_SUITES:
        record = evaluate_and_heal_loop(
            raw_text=suite["raw_text"], gold_event=suite["gold"], threshold=90.0, max_retries=5
        )
        # Starting from the rules means the first attempt is the rules' own answer.
        assert record.initial_metrics == record.iterations[0].metrics


def test_adversarial_suite_does_not_pass_and_is_not_made_to():
    """Pinned on purpose: nobody should quietly turn this one green."""
    suite = _suite("suite_adversarial_guardrails")
    record = evaluate_and_heal_loop(
        raw_text=suite["raw_text"], gold_event=suite["gold"], threshold=90.0, max_retries=5
    )
    assert record.passed is False
    assert record.final_score < 90.0
    assert record.total_retries == 5


@pytest.mark.parametrize(
    "suite_id,expected_pass",
    [
        ("suite_negation_intent", True),
        ("suite_dietary_allergens", True),
        ("suite_secondary_roommate", True),
        ("suite_adversarial_guardrails", False),
    ],
)
def test_each_suite_passes_or_fails_as_documented(suite_id, expected_pass):
    suite = _suite(suite_id)
    record = evaluate_and_heal_loop(
        raw_text=suite["raw_text"], gold_event=suite["gold"], threshold=90.0, max_retries=5
    )
    assert record.passed is expected_pass


def test_lab_page_states_its_limits(client):
    text = client.get("/benchmarks").text
    assert "Scorer demo. Needs gold labels." in text
    assert "is not used when you paste a chat" in text
    assert "The adversarial suite is expected to fail." in text
    assert "self-heal" not in text.lower()


def test_pasting_a_chat_never_touches_the_benchmark_lab(monkeypatch):
    """The lab is not in the paste path."""
    import tiffintally.benchmarks as benchmarks

    calls = []
    original = benchmarks.evaluate_and_heal_loop
    monkeypatch.setattr(
        benchmarks, "evaluate_and_heal_loop", lambda *a, **k: calls.append(a) or original(*a, **k)
    )
    monkeypatch.setattr("tiffintally.app.evaluate_and_heal_loop", benchmarks.evaluate_and_heal_loop)

    client = TestClient(app)
    response = client.post(
        "/process",
        data={"raw_text": "17/10/2026, 8:00 pm - Asha: kal lunch 2", "target_date": "tomorrow"},
    )
    assert response.status_code == 200
    assert calls == []
