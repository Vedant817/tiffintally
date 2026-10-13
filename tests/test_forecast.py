"""Tests for TabPFN and historical kitchen forecasting."""

from tiffintally.forecast import KitchenForecaster, load_and_preprocess_history


def test_load_and_preprocess_history():
    df = load_and_preprocess_history()
    assert len(df) >= 30
    assert "actual_cooked" in df.columns
    assert "confirmed_orders" in df.columns
    assert "lag7_cooked" in df.columns


def test_forecast_evaluation_benchmarks():
    forecaster = KitchenForecaster(api_key=None)
    df = load_and_preprocess_history()
    _, benchmark = forecaster.fit_and_evaluate(df, test_days=14)

    assert benchmark.n_train > 0
    assert benchmark.n_test == 14
    assert benchmark.tabpfn_mae >= 0.0
    assert benchmark.naive_lag7_mae >= 0.0
    assert benchmark.confirmed_only_mae >= 0.0
    # Model should perform reasonably (MAE typically < 5 plates)
    assert benchmark.tabpfn_mae < 10.0


def test_how_many_to_cook_agent_tool():
    forecaster = KitchenForecaster(api_key=None)
    res = forecaster.how_many_to_cook(target_date="2026-10-15", confirmed_count=41)

    assert res.target_date == "2026-10-15"
    assert res.confirmed_orders == 41
    # Predicted plates should be at least confirmed orders
    assert res.predicted_to_cook >= 41
    assert res.recommended_buffer >= 0
    assert "thalis" in res.explanation
