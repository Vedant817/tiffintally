"""Tests for evaluation metrics and benchmark harness."""

from tiffintally.eval import MetricScore, compute_f1


def test_compute_f1_perfect_match():
    gold = ["lunch", "dinner", "lunch"]
    pred = ["lunch", "dinner", "lunch"]
    score = compute_f1(gold, pred)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_compute_f1_partial_mismatch():
    gold = ["lunch", "dinner", "lunch", "lunch"]
    pred = ["lunch", "lunch", "lunch", "dinner"]
    score = compute_f1(gold, pred)
    assert 0.0 < score.f1 < 1.0
    assert isinstance(score, MetricScore)


def test_compute_f1_empty():
    gold = []
    pred = []
    score = compute_f1(gold, pred)
    assert score.f1 == 0.0 or score.f1 == 1.0
