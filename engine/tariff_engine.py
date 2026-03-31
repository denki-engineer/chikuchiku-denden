"""Tariff lookup and attachment helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from chikuchiku_denden.engine.calendar_engine import (
        TIME_SLOTS,
        compute_tariff_holiday_mask,
        ensure_energy_columns,
    )
    from chikuchiku_denden.models import TariffPlan
except ModuleNotFoundError:
    from engine.calendar_engine import TIME_SLOTS, compute_tariff_holiday_mask, ensure_energy_columns
    from models import TariffPlan

DAY_TYPE_TO_INDEX = {"weekday": 0, "holiday": 1}


def build_tariff_lookup_array(tariff_df: pd.DataFrame) -> np.ndarray:
    """Convert tariff DataFrame into [13, 2, 48] lookup array."""

    lookup = np.full((13, 2, len(TIME_SLOTS)), np.nan, dtype=float)
    time_slot_index = {slot: index for index, slot in enumerate(TIME_SLOTS)}
    tariff_rows = tariff_df[["month", "day_type", "time_slot", "unit_price"]].copy()
    tariff_rows["month"] = pd.to_numeric(tariff_rows["month"], errors="raise").astype(int)
    tariff_rows["unit_price"] = pd.to_numeric(tariff_rows["unit_price"], errors="raise").astype(float)
    for row in tariff_rows.itertuples(index=False):
        lookup[int(row.month), DAY_TYPE_TO_INDEX[str(row.day_type)], time_slot_index[str(row.time_slot)]] = float(row.unit_price)
    if np.isnan(lookup[1:]).any():
        raise ValueError("tariff lookup の生成に失敗しました。")
    return lookup


def attach_tariff_prices(energy_df: pd.DataFrame, plan: TariffPlan, prefix: str) -> pd.DataFrame:
    """Attach tariff day type and unit price columns without row-wise apply."""

    df = ensure_energy_columns(energy_df)
    holiday_mask = compute_tariff_holiday_mask(df["datetime"], plan.holiday_list)
    day_type_index = holiday_mask.astype(int)
    lookup = build_tariff_lookup_array(plan.tariff_df)
    prices = lookup[df["month"].to_numpy(dtype=int), day_type_index, df["time_slot_index"].to_numpy(dtype=int)]
    working = df.copy()
    working[f"{prefix}_tariff_day_type"] = np.where(holiday_mask, "holiday", "weekday")
    working[f"{prefix}_unit_price"] = prices
    return working
