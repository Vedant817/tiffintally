"""Tests for AI Lab Benchmarking, Evaluation Metrics, and Auto-Repair Loop."""

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
    assert "AI Model Benchmark & Metric Repair Lab" in res.text

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
