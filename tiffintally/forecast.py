"""
Kitchen plate forecast.

The default model is scikit-learn HistGradientBoosting on data/kitchen_history.csv,
which is synthetic. TabPFN is used only when TABPFN_API_KEY is set and the client
imports. TabPFN's client licence is non-commercial. This module does not estimate
rupee savings.
"""

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = Path("data/kitchen_history.csv")

# Known Indian Holidays 2026 for feature engineering
INDIAN_HOLIDAYS = {
    "2026-08-15": "Independence Day",
    "2026-08-28": "Raksha Bandhan",
    "2026-09-04": "Janmashtami",
    "2026-10-02": "Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-08": "Diwali",
    "2026-11-09": "Govardhan Puja",
}


class ForecastResult(BaseModel):
    target_date: str
    confirmed_orders: int
    predicted_to_cook: int
    recommended_buffer: int
    model_used: str
    is_synthetic_history: bool
    explanation: str


class ForecastBenchmark(BaseModel):
    n_train: int
    n_test: int
    is_synthetic: bool
    model_name: str
    tabpfn_mae: float
    tabpfn_rmse: float
    tabpfn_within_3: float
    naive_lag7_mae: float
    naive_lag7_rmse: float
    naive_within_3: float
    confirmed_only_mae: float
    confirmed_only_rmse: float
    confirmed_within_3: float


def load_and_preprocess_history(csv_path: Optional[Path] = None) -> pd.DataFrame:
    path = csv_path or DEFAULT_HISTORY_PATH
    if not path.exists():
        # Auto-generate if missing
        from scripts.gen_history import generate_kitchen_history

        records = generate_kitchen_history()
        df = pd.DataFrame(records)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
    else:
        df = pd.read_csv(path)

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


class KitchenForecaster:
    """Forecaster for tiffin plates using TabPFN or scikit-learn fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TABPFN_API_KEY")
        self._model = None
        self._model_type = "none"

    def is_tabpfn_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _get_regressor(self):
        if self.is_tabpfn_available():
            try:
                import tabpfn_client

                tabpfn_client.set_access_token(self.api_key)
                from tabpfn_client import TabPFNRegressor

                self._model_type = "TabPFN-v2"
                return TabPFNRegressor()
            except Exception as e:
                logger.warning(
                    f"TabPFN initialization failed: {e}. Using HistGradientBoosting fallback."
                )

        self._model_type = "HistGradientBoosting-Fallback"
        return HistGradientBoostingRegressor(random_state=42, max_iter=100)

    def fit_and_evaluate(
        self, df: pd.DataFrame, test_days: int = 14
    ) -> Tuple[Any, ForecastBenchmark]:
        """
        Time-based train/test split (no data leakage or shuffling).
        Computes TabPFN (or fallback) vs Naive lag-7 vs Confirmed-only.
        """
        features = [
            "day_of_week",
            "is_weekend",
            "is_holiday",
            "confirmed_orders",
            "lag7_cooked",
            "rolling7_mean",
        ]
        target = "actual_cooked"

        # Time split
        split_idx = len(df) - test_days
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        X_train = train_df[features]
        y_train = train_df[target]
        X_test = test_df[features]
        y_test = test_df[target]

        model = self._get_regressor()
        model.fit(X_train, y_train)

        # 1. Model predictions
        preds = model.predict(X_test)
        preds = np.round(preds).astype(int)

        mae_model = float(mean_absolute_error(y_test, preds))
        rmse_model = float(root_mean_squared_error(y_test, preds))
        within_3_model = float(np.mean(np.abs(y_test - preds) <= 3) * 100.0)

        # 2. Naive lag-7 baseline (same weekday last week)
        naive_preds = test_df["lag7_cooked"].values
        mae_naive = float(mean_absolute_error(y_test, naive_preds))
        rmse_naive = float(root_mean_squared_error(y_test, naive_preds))
        within_3_naive = float(np.mean(np.abs(y_test - naive_preds) <= 3) * 100.0)

        # 3. Confirmed-only baseline
        conf_preds = test_df["confirmed_orders"].values
        mae_conf = float(mean_absolute_error(y_test, conf_preds))
        rmse_conf = float(root_mean_squared_error(y_test, conf_preds))
        within_3_conf = float(np.mean(np.abs(y_test - conf_preds) <= 3) * 100.0)

        benchmark = ForecastBenchmark(
            n_train=len(train_df),
            n_test=len(test_df),
            is_synthetic=True,
            model_name=self._model_type,
            tabpfn_mae=round(mae_model, 2),
            tabpfn_rmse=round(rmse_model, 2),
            tabpfn_within_3=round(within_3_model, 1),
            naive_lag7_mae=round(mae_naive, 2),
            naive_lag7_rmse=round(rmse_naive, 2),
            naive_within_3=round(within_3_naive, 1),
            confirmed_only_mae=round(mae_conf, 2),
            confirmed_only_rmse=round(rmse_conf, 2),
            confirmed_within_3=round(within_3_conf, 1),
        )

        return model, benchmark

    def how_many_to_cook(
        self,
        target_date: Optional[str] = None,
        confirmed_count: int = 0,
        history_csv: Optional[Path] = None,
    ) -> ForecastResult:
        """
        Agent tool / UI function: Predict plates to cook for target date.
        """
        df = load_and_preprocess_history(history_csv)

        # Target date defaults to tomorrow
        if target_date in [None, "tomorrow", ""]:
            t_date = (date.today() + timedelta(days=1)).isoformat()
        elif target_date == "today":
            t_date = date.today().isoformat()
        else:
            t_date = target_date

        dt = datetime.fromisoformat(t_date).date()
        dow = dt.weekday()
        is_wknd = 1 if dow in [5, 6] else 0
        is_hol = 1 if t_date in INDIAN_HOLIDAYS else 0

        # Lags from recent rows
        recent_cooked = df["actual_cooked"].tail(14).values
        lag7 = int(recent_cooked[-7]) if len(recent_cooked) >= 7 else confirmed_count + 4
        roll7 = (
            float(np.mean(recent_cooked[-7:]))
            if len(recent_cooked) >= 7
            else float(confirmed_count + 3)
        )

        model, _ = self.fit_and_evaluate(df, test_days=14)

        X_input = pd.DataFrame(
            [
                {
                    "day_of_week": dow,
                    "is_weekend": is_wknd,
                    "is_holiday": is_hol,
                    "confirmed_orders": confirmed_count,
                    "lag7_cooked": lag7,
                    "rolling7_mean": roll7,
                }
            ]
        )

        pred_raw = model.predict(X_input)[0]
        # Never cook less than confirmed orders
        pred_plates = max(confirmed_count, int(np.round(pred_raw)))
        buffer = pred_plates - confirmed_count

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_name = day_names[dow]

        if self._model_type.startswith("TabPFN"):
            licence = " TabPFN's client licence is non-commercial. History file is still synthetic."
        else:
            licence = (
                " No TabPFN call was made. The history file is synthetic, so this buffer"
                " is not a measured saving."
            )
        explanation = (
            f"Based on {dow_name} history and {confirmed_count} confirmed orders, "
            f"the model suggests a buffer of {buffer}. Cook the {confirmed_count} from the chat. "
            f"Do not add the buffer to the pot."
            f" Model: {self._model_type}.{licence}"
        )

        return ForecastResult(
            target_date=t_date,
            confirmed_orders=confirmed_count,
            predicted_to_cook=pred_plates,
            recommended_buffer=buffer,
            model_used=self._model_type,
            is_synthetic_history=True,
            explanation=explanation,
        )
