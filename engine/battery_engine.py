"""Battery simulation engine.

The time-series state update depends on the previous step's battery energy,
so full vectorization would obscure the business rules. We instead keep a
single tight loop over NumPy arrays and precompute every lookup used inside it.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

try:
    from chikuchiku_denden.engine.calendar_engine import build_operation_calendar, ensure_energy_columns
    from chikuchiku_denden.engine.tariff_engine import attach_tariff_prices
    from chikuchiku_denden.models import BatteryParams, SimulationResult, TariffPlan
except ModuleNotFoundError:
    from engine.calendar_engine import build_operation_calendar, ensure_energy_columns
    from engine.tariff_engine import attach_tariff_prices
    from models import BatteryParams, SimulationResult, TariffPlan

HALF_HOUR_HOURS = 0.5
OPERATING_DAY_INDEX = {"operating": 0, "holiday": 1}
SCHEDULE_DAY_LABELS = ("稼働日", "休業日")
SCHEDULE_MODE_NAMES = ("固定(kW)", "GRID目標(kW)", "容量目標(kWh)")


def determine_active_mode_for_values(fixed_kw: float, grid_target_kw: float, energy_target_kwh: float) -> str:
    if not np.isnan(fixed_kw):
        return "fixed"
    if not np.isnan(grid_target_kw):
        return "grid_target"
    if not np.isnan(energy_target_kwh):
        return "energy_target"
    return "none"


def clip_battery_power_by_limits(
    raw_power_kw: float,
    power_limit_kw: float,
    current_energy_kwh: float,
    capacity_kwh: float,
) -> float:
    upper_limit = min(power_limit_kw, (capacity_kwh - current_energy_kwh) / HALF_HOUR_HOURS)
    lower_limit = max(-power_limit_kw, -current_energy_kwh / HALF_HOUR_HOURS)
    return max(lower_limit, min(upper_limit, raw_power_kw))


def compile_schedule_lookup(battery_schedule_df: pd.DataFrame) -> np.ndarray:
    """Compile wide schedule DataFrame into [13, 2, 48, 3] float array."""

    schedule_lookup = np.full((13, 2, 48, 3), np.nan, dtype=float)
    for month in range(1, 13):
        for day_index, day_label in enumerate(SCHEDULE_DAY_LABELS):
            for mode_index, mode_name in enumerate(SCHEDULE_MODE_NAMES):
                column_name = f"{month}月_{day_label}_{mode_name}"
                schedule_lookup[month, day_index, :, mode_index] = pd.to_numeric(
                    battery_schedule_df[column_name],
                    errors="coerce",
                ).to_numpy(dtype=float)
    return schedule_lookup


def simulate_battery(
    energy_df: pd.DataFrame,
    battery_params: BatteryParams,
    battery_schedule_df: pd.DataFrame,
    operation_holiday_list: list[str],
    planA: TariffPlan,
    planB: TariffPlan,
) -> SimulationResult:
    """Run annual battery simulation.

    Benchmark tip:
    `benchmark_simulation_once(...)` can be used from a Python shell to measure
    the engine in isolation without Streamlit rerun overhead.
    """

    battery_params.validate()
    planA.validate()
    planB.validate()

    df = build_operation_calendar(energy_df, operation_holiday_list)
    df = attach_tariff_prices(df, planA, "planA")
    df = attach_tariff_prices(df, planB, "planB")

    schedule_lookup = compile_schedule_lookup(battery_schedule_df)
    row_count = len(df)
    datetime_values = pd.to_datetime(df["datetime"], errors="raise")
    month_values = df["month"].to_numpy(dtype=int)
    time_slot_index = df["time_slot_index"].to_numpy(dtype=int)
    operation_day_index = np.where(df["operation_day_type"].to_numpy() == "holiday", 1, 0).astype(int)
    original_grid_kw = df["original_grid_kw_30min_avg"].to_numpy(dtype=float)
    original_grid_kwh = df["kWh"].to_numpy(dtype=float)
    planA_unit_price = df["planA_unit_price"].to_numpy(dtype=float)
    planB_unit_price = df["planB_unit_price"].to_numpy(dtype=float)

    battery_kw = np.zeros(row_count, dtype=float)
    battery_kwh_30min = np.zeros(row_count, dtype=float)
    adjusted_grid_kw = np.zeros(row_count, dtype=float)
    adjusted_grid_kwh = np.zeros(row_count, dtype=float)
    battery_energy_kwh = np.zeros(row_count, dtype=float)
    active_modes = np.empty(row_count, dtype=object)

    current_energy_kwh = min(battery_params.battery_capacity_kwh, battery_params.battery_initial_energy_kwh)
    if row_count > 0:
        current_energy_kwh = max(0.0, current_energy_kwh)

    # TODO: SoC 更新は前時点に依存するため単一ループを維持している。
    # 将来的に更なる高速化が必要なら、Numba 等でこのループ自体を高速化する余地がある。
    for index in range(row_count):
        month = month_values[index]
        day_type_index = operation_day_index[index]
        slot_index = time_slot_index[index]
        fixed_kw, grid_target_kw, energy_target_kwh = schedule_lookup[month, day_type_index, slot_index]
        active_mode = determine_active_mode_for_values(fixed_kw, grid_target_kw, energy_target_kwh)
        if active_mode == "fixed":
            raw_power_kw = float(fixed_kw)
        elif active_mode == "grid_target":
            raw_power_kw = float(grid_target_kw) - original_grid_kw[index]
        elif active_mode == "energy_target":
            raw_power_kw = (float(energy_target_kwh) - current_energy_kwh) / HALF_HOUR_HOURS
        else:
            raw_power_kw = 0.0

        current_power_kw = clip_battery_power_by_limits(
            raw_power_kw=raw_power_kw,
            power_limit_kw=battery_params.battery_power_limit_kw,
            current_energy_kwh=current_energy_kwh,
            capacity_kwh=battery_params.battery_capacity_kwh,
        )
        current_energy_kwh = max(
            0.0,
            min(battery_params.battery_capacity_kwh, current_energy_kwh + current_power_kw * HALF_HOUR_HOURS),
        )

        battery_kw[index] = current_power_kw
        battery_kwh_30min[index] = current_power_kw * HALF_HOUR_HOURS
        adjusted_grid_kw[index] = original_grid_kw[index] + current_power_kw
        adjusted_grid_kwh[index] = adjusted_grid_kw[index] * HALF_HOUR_HOURS
        battery_energy_kwh[index] = current_energy_kwh
        active_modes[index] = active_mode

    timeseries_df = pd.DataFrame(
        {
            "datetime": datetime_values,
            "month": month_values,
            "date": datetime_values.dt.strftime("%Y-%m-%d"),
            "time": datetime_values.dt.strftime("%H:%M"),
            "time_slot": df["time_slot"].to_numpy(),
            "operation_day_type": df["operation_day_type"].to_numpy(),
            "original_grid_kwh_30min": original_grid_kwh,
            "original_grid_kw_30min_avg": original_grid_kw,
            "battery_kw": battery_kw,
            "battery_kwh_30min": battery_kwh_30min,
            "adjusted_grid_kwh_30min": adjusted_grid_kwh,
            "adjusted_grid_kw_30min_avg": adjusted_grid_kw,
            "battery_energy_kwh": battery_energy_kwh,
            "active_mode": active_modes,
            "planA_unit_price": planA_unit_price,
            "planB_unit_price": planB_unit_price,
        }
    )
    monthly_summary_df = summarize_monthly_results(timeseries_df, planA, planB)
    annual_summary_df = summarize_annual_results(timeseries_df, planA, planB)
    representative_week_df = select_representative_week(timeseries_df)
    return SimulationResult(
        timeseries_df=timeseries_df,
        monthly_summary_df=monthly_summary_df,
        annual_summary_df=annual_summary_df,
        representative_week_df=representative_week_df,
    )


def summarize_monthly_results(timeseries_df: pd.DataFrame, planA: TariffPlan, planB: TariffPlan) -> pd.DataFrame:
    """Aggregate monthly results without redoing tariff lookup."""

    _ = planA, planB
    working = timeseries_df.assign(
        planA_energy_cost_before=timeseries_df["original_grid_kwh_30min"] * timeseries_df["planA_unit_price"],
        planA_energy_cost_after=timeseries_df["adjusted_grid_kwh_30min"] * timeseries_df["planA_unit_price"],
        planB_energy_cost_before=timeseries_df["original_grid_kwh_30min"] * timeseries_df["planB_unit_price"],
        planB_energy_cost_after=timeseries_df["adjusted_grid_kwh_30min"] * timeseries_df["planB_unit_price"],
    )
    summary = (
        working.groupby("month", as_index=False)
        .agg(
            max_grid_kw_before=("original_grid_kw_30min_avg", "max"),
            max_grid_kw_after=("adjusted_grid_kw_30min_avg", "max"),
            planA_energy_cost_before=("planA_energy_cost_before", "sum"),
            planA_energy_cost_after=("planA_energy_cost_after", "sum"),
            planB_energy_cost_before=("planB_energy_cost_before", "sum"),
            planB_energy_cost_after=("planB_energy_cost_after", "sum"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    summary["delta_max_grid_kw"] = summary["max_grid_kw_after"] - summary["max_grid_kw_before"]
    summary["delta_planA_energy_cost"] = summary["planA_energy_cost_after"] - summary["planA_energy_cost_before"]
    summary["delta_planB_energy_cost"] = summary["planB_energy_cost_after"] - summary["planB_energy_cost_before"]
    return summary[
        [
            "month",
            "max_grid_kw_before",
            "max_grid_kw_after",
            "delta_max_grid_kw",
            "planA_energy_cost_before",
            "planA_energy_cost_after",
            "delta_planA_energy_cost",
            "planB_energy_cost_before",
            "planB_energy_cost_after",
            "delta_planB_energy_cost",
        ]
    ]


def summarize_annual_results(timeseries_df: pd.DataFrame, planA: TariffPlan, planB: TariffPlan) -> pd.DataFrame:
    annual_max_grid_kw_before = float(timeseries_df["original_grid_kw_30min_avg"].max())
    annual_max_grid_kw_after = float(timeseries_df["adjusted_grid_kw_30min_avg"].max())
    planA_basic_cost_before = annual_max_grid_kw_before * planA.basic_rate_yen_per_kw_month * 12
    planA_basic_cost_after = annual_max_grid_kw_after * planA.basic_rate_yen_per_kw_month * 12
    planA_energy_cost_before = float((timeseries_df["original_grid_kwh_30min"] * timeseries_df["planA_unit_price"]).sum())
    planA_energy_cost_after = float((timeseries_df["adjusted_grid_kwh_30min"] * timeseries_df["planA_unit_price"]).sum())
    planB_basic_cost_before = annual_max_grid_kw_before * planB.basic_rate_yen_per_kw_month * 12
    planB_basic_cost_after = annual_max_grid_kw_after * planB.basic_rate_yen_per_kw_month * 12
    planB_energy_cost_before = float((timeseries_df["original_grid_kwh_30min"] * timeseries_df["planB_unit_price"]).sum())
    planB_energy_cost_after = float((timeseries_df["adjusted_grid_kwh_30min"] * timeseries_df["planB_unit_price"]).sum())
    return pd.DataFrame(
        [
            {
                "annual_max_grid_kw_before": annual_max_grid_kw_before,
                "annual_max_grid_kw_after": annual_max_grid_kw_after,
                "planA_basic_cost_before": planA_basic_cost_before,
                "planA_basic_cost_after": planA_basic_cost_after,
                "planA_energy_cost_before": planA_energy_cost_before,
                "planA_energy_cost_after": planA_energy_cost_after,
                "planA_total_cost_before": planA_basic_cost_before + planA_energy_cost_before,
                "planA_total_cost_after": planA_basic_cost_after + planA_energy_cost_after,
                "delta_planA_total_cost": (planA_basic_cost_after + planA_energy_cost_after) - (planA_basic_cost_before + planA_energy_cost_before),
                "planB_basic_cost_before": planB_basic_cost_before,
                "planB_basic_cost_after": planB_basic_cost_after,
                "planB_energy_cost_before": planB_energy_cost_before,
                "planB_energy_cost_after": planB_energy_cost_after,
                "planB_total_cost_before": planB_basic_cost_before + planB_energy_cost_before,
                "planB_total_cost_after": planB_basic_cost_after + planB_energy_cost_after,
                "delta_planB_total_cost": (planB_basic_cost_after + planB_energy_cost_after) - (planB_basic_cost_before + planB_energy_cost_before),
            }
        ]
    )


def select_representative_week(timeseries_df: pd.DataFrame) -> pd.DataFrame:
    df = timeseries_df.copy()
    df["week_start"] = (df["datetime"] - pd.to_timedelta(df["datetime"].dt.weekday, unit="D")).dt.normalize()
    candidates = (
        df.groupby("week_start", as_index=False)
        .agg(
            peak_before=("original_grid_kw_30min_avg", "max"),
            battery_abs_sum=("battery_kw", lambda values: values.abs().sum()),
        )
        .sort_values(["peak_before", "battery_abs_sum", "week_start"], ascending=[False, False, True])
    )
    selected = candidates.iloc[0]["week_start"]
    return df[df["week_start"] == selected].copy()


def build_step6_assumption_text() -> str:
    return (
        "料金単価はユーザー入力に基づきます。"
        "\n基本料金と従量料金のみを対象としています。"
        "\n再エネ賦課金、燃料費調整額、市場価格調整額等は含みません。"
        "\n蓄電池効率・損失・劣化・SoC制約は考慮していません。"
        "\n太陽光等の発電設備は考慮していません。"
        "\n実績データに基づく概算であり、将来条件により変動し得ます。"
        "\n投資判断の参考情報であり、実額を保証するものではありません。"
    )


def benchmark_simulation_once(
    energy_df: pd.DataFrame,
    battery_params: BatteryParams,
    battery_schedule_df: pd.DataFrame,
    operation_holiday_list: list[str],
    planA: TariffPlan,
    planB: TariffPlan,
) -> dict[str, Any]:
    """Small benchmark helper for manual profiling from a Python shell."""

    started_at = perf_counter()
    result = simulate_battery(energy_df, battery_params, battery_schedule_df, operation_holiday_list, planA, planB)
    elapsed_seconds = perf_counter() - started_at
    return {
        "elapsed_seconds": elapsed_seconds,
        "rows": len(result.timeseries_df),
        "battery_params": asdict(battery_params),
    }
