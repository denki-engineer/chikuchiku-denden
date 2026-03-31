"""Calendar and time-series preparation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

HALF_HOUR_FREQ = "30min"
TIME_SLOTS = [
    f"{hour:02d}:{minute:02d}-" + ("24:00" if hour == 23 and minute == 30 else f"{(hour + (1 if minute == 30 else 0)):02d}:{(minute + 30) % 60:02d}")
    for hour in range(24)
    for minute in (0, 30)
]
TIME_SLOT_TO_INDEX = {slot: index for index, slot in enumerate(TIME_SLOTS)}


def normalize_mmdd(value: str) -> str:
    """Normalize `M/D` or `MM-DD` to `MM-DD`."""

    month_text, day_text = str(value).strip().replace("-", "/").split("/")
    return f"{int(month_text):02d}-{int(day_text):02d}"


def parse_holiday_text(text: str) -> list[str]:
    """Parse newline/comma separated holiday input."""

    values: list[str] = []
    for raw in text.replace(",", "\n").splitlines():
        item = raw.strip()
        if item:
            values.append(item.replace("-", "/"))
    return values


def get_time_slot_label(ts: pd.Timestamp) -> str:
    """Return 30-minute slot label."""

    start = ts.strftime("%H:%M")
    end_ts = ts + pd.Timedelta(minutes=30)
    end = "24:00" if ts.hour == 23 and ts.minute == 30 else end_ts.strftime("%H:%M")
    return f"{start}-{end}"


def mmdd_series_from_datetime(datetime_series: pd.Series) -> pd.Series:
    return datetime_series.dt.strftime("%m-%d")


def _holiday_set(holiday_list: list[str]) -> set[str]:
    return {normalize_mmdd(value) for value in holiday_list}


def is_tariff_holiday(date_value: pd.Timestamp, holiday_list: list[str]) -> bool:
    holiday_set = _holiday_set(holiday_list)
    return date_value.weekday() == 6 or normalize_mmdd(f"{date_value.month}/{date_value.day}") in holiday_set


def is_operation_holiday(date_value: pd.Timestamp, operation_holiday_list: list[str]) -> bool:
    holiday_set = _holiday_set(operation_holiday_list)
    return date_value.weekday() >= 5 or normalize_mmdd(f"{date_value.month}/{date_value.day}") in holiday_set


def classify_operation_day(date_value: pd.Timestamp, operation_holiday_list: list[str]) -> str:
    return "holiday" if is_operation_holiday(date_value, operation_holiday_list) else "operating"


def ensure_energy_columns(energy_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare required energy-series columns once."""

    df = energy_df.copy()
    if "datetime" not in df.columns:
        df["datetime"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="raise")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="raise")
    df = df.sort_values("datetime").reset_index(drop=True)
    df["kWh"] = pd.to_numeric(df["kWh"], errors="raise")
    if "original_grid_kw_30min_avg" not in df.columns:
        df["original_grid_kw_30min_avg"] = df["kWh"] * 2
    else:
        df["original_grid_kw_30min_avg"] = pd.to_numeric(df["original_grid_kw_30min_avg"], errors="raise")
    df["month"] = df["datetime"].dt.month.astype(int)
    time_slot_index = df["datetime"].dt.hour * 2 + (df["datetime"].dt.minute // 30)
    df["time_slot_index"] = time_slot_index.astype(int)
    if "time_slot" not in df.columns:
        df["time_slot"] = time_slot_index.map(lambda index: TIME_SLOTS[int(index)])
    return df


def attach_operation_day_type(energy_df: pd.DataFrame, operation_holiday_list: list[str], column_name: str = "operation_day_type") -> pd.DataFrame:
    df = ensure_energy_columns(energy_df)
    holiday_mask = compute_operation_holiday_mask(df["datetime"], operation_holiday_list)
    df[column_name] = np.where(holiday_mask, "holiday", "operating")
    return df


def compute_tariff_holiday_mask(datetime_series: pd.Series, holiday_list: list[str]) -> np.ndarray:
    mmdd = mmdd_series_from_datetime(datetime_series)
    holiday_mask = mmdd.isin(_holiday_set(holiday_list)).to_numpy()
    sunday_mask = datetime_series.dt.weekday.eq(6).to_numpy()
    return np.logical_or(holiday_mask, sunday_mask)


def compute_operation_holiday_mask(datetime_series: pd.Series, operation_holiday_list: list[str]) -> np.ndarray:
    mmdd = mmdd_series_from_datetime(datetime_series)
    holiday_mask = mmdd.isin(_holiday_set(operation_holiday_list)).to_numpy()
    weekend_mask = datetime_series.dt.weekday.ge(5).to_numpy()
    return np.logical_or(holiday_mask, weekend_mask)


def build_operation_calendar(energy_df: pd.DataFrame, operation_holiday_list: list[str]) -> pd.DataFrame:
    return attach_operation_day_type(energy_df, operation_holiday_list)

