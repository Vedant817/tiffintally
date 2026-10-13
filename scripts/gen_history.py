"""
Generate 90 days of synthetic daily kitchen order and cooking history for TabPFN training.
Reflects Indian home kitchen realities:
- Day-of-week seasonality (Sunday drops, Monday surges, Friday highs)
- Indian festival drops (Diwali, Raksha Bandhan)
- Late doorstep orders (confirmed + late walk-ins = actual cooked)
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

OUTPUT_CSV = Path("data/kitchen_history.csv")

# Known Indian holidays 2026 within the 90-day window (approx Aug - Oct 2026)
INDIAN_HOLIDAYS_2026 = {
    date(2026, 8, 15): "Independence Day",
    date(2026, 8, 28): "Raksha Bandhan",
    date(2026, 9, 4): "Janmashtami",
    date(2026, 10, 2): "Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
}


def generate_kitchen_history(
    start_date: date = date(2026, 7, 15), days: int = 90
) -> List[Dict[str, Any]]:
    random.seed(42)
    records = []

    # Track rolling window for lags
    cooked_history: List[int] = []

    # Prime history with 14 dummy days before start
    for _ in range(14):
        cooked_history.append(random.randint(35, 45))

    for day_idx in range(days):
        curr_date = start_date + timedelta(days=day_idx)
        dow = curr_date.weekday()  # 0=Monday, 6=Sunday
        is_weekend = 1 if dow in [5, 6] else 0
        is_holiday = 1 if curr_date in INDIAN_HOLIDAYS_2026 else 0

        # Day-of-week base confirmed demand
        dow_factor = {
            0: 48,  # Monday surge
            1: 44,  # Tuesday steady
            2: 43,  # Wednesday steady
            3: 45,  # Thursday steady
            4: 42,  # Friday slight drop
            5: 32,  # Saturday many go out
            6: 18,  # Sunday kitchen half-day or student leaves
        }[dow]

        noise = random.randint(-4, 4)
        confirmed = max(10, dow_factor + noise)

        if is_holiday:
            confirmed = int(confirmed * 0.4)

        # Late doorstep walk-ins: 2 to 8 plates depending on weekday
        if dow in [0, 1, 2, 3]:
            late_walkins = random.randint(3, 7)
        elif dow in [4, 5]:
            late_walkins = random.randint(1, 4)
        else:
            late_walkins = random.randint(0, 2)

        if is_holiday:
            late_walkins = random.randint(0, 1)

        actual_cooked = confirmed + late_walkins

        # Features
        lag7 = cooked_history[-7]
        rolling7 = round(sum(cooked_history[-7:]) / 7.0, 1)

        records.append(
            {
                "date": curr_date.isoformat(),
                "day_of_week": dow,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "confirmed_orders": confirmed,
                "late_walkins": late_walkins,
                "actual_cooked": actual_cooked,
                "lag7_cooked": lag7,
                "rolling7_mean": rolling7,
            }
        )

        cooked_history.append(actual_cooked)

    return records


def main():
    records = generate_kitchen_history()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    print(f"Generated {len(records)} days of kitchen history at {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
