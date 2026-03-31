"""Backwards-compatible facade over the pure engine modules."""

from __future__ import annotations

try:
    from chikuchiku_denden.engine.battery_engine import (
        HALF_HOUR_HOURS,
        benchmark_simulation_once,
        build_step6_assumption_text,
        clip_battery_power_by_limits,
        compile_schedule_lookup,
        determine_active_mode_for_values,
        select_representative_week,
        simulate_battery,
        summarize_annual_results,
        summarize_monthly_results,
    )
    from chikuchiku_denden.engine.calendar_engine import (
        TIME_SLOTS,
        build_operation_calendar,
        classify_operation_day,
        ensure_energy_columns as _ensure_energy_columns,
        get_time_slot_label,
        is_operation_holiday,
        is_tariff_holiday,
        normalize_mmdd,
        parse_holiday_text,
    )
    from chikuchiku_denden.engine.step2_engine import calculate_step2
    from chikuchiku_denden.engine.step3_engine import calculate_step3
    from chikuchiku_denden.engine.tariff_engine import (
        attach_tariff_prices as _attach_tariff_prices,
        build_tariff_lookup_array,
    )
except ModuleNotFoundError:  # app.py direct execution
    from engine.battery_engine import (
        HALF_HOUR_HOURS,
        benchmark_simulation_once,
        build_step6_assumption_text,
        clip_battery_power_by_limits,
        compile_schedule_lookup,
        determine_active_mode_for_values,
        select_representative_week,
        simulate_battery,
        summarize_annual_results,
        summarize_monthly_results,
    )
    from engine.calendar_engine import (
        TIME_SLOTS,
        build_operation_calendar,
        classify_operation_day,
        ensure_energy_columns as _ensure_energy_columns,
        get_time_slot_label,
        is_operation_holiday,
        is_tariff_holiday,
        normalize_mmdd,
        parse_holiday_text,
    )
    from engine.step2_engine import calculate_step2
    from engine.step3_engine import calculate_step3
    from engine.tariff_engine import attach_tariff_prices as _attach_tariff_prices, build_tariff_lookup_array


def determine_active_mode_for_row(schedule_row) -> str:
    return determine_active_mode_for_values(
        schedule_row.get("fixed_kw"),
        schedule_row.get("grid_target_kw"),
        schedule_row.get("energy_target_kwh"),
    )


def get_schedule_values_for_timestamp(
    battery_schedule_df,
    month: int,
    operation_day_type: str,
    time_slot: str,
):
    day_index = 0 if operation_day_type == "operating" else 1
    schedule_lookup = compile_schedule_lookup(battery_schedule_df)
    time_slot_row = battery_schedule_df.index[battery_schedule_df["time_slot"] == time_slot]
    if len(time_slot_row) == 0:
        raise ValueError(f"スケジュールに time_slot={time_slot} がありません。")
    fixed_kw, grid_target_kw, energy_target_kwh = schedule_lookup[int(month), day_index, int(time_slot_row[0])]
    return {
        "fixed_kw": fixed_kw,
        "grid_target_kw": grid_target_kw,
        "energy_target_kwh": energy_target_kwh,
    }


def calculate_battery_power_for_row(original_grid_kw, current_energy_kwh, battery_params, schedule_values):
    active_mode = determine_active_mode_for_values(
        schedule_values.get("fixed_kw"),
        schedule_values.get("grid_target_kw"),
        schedule_values.get("energy_target_kwh"),
    )
    if active_mode == "fixed":
        raw_power_kw = float(schedule_values["fixed_kw"])
    elif active_mode == "grid_target":
        raw_power_kw = float(schedule_values["grid_target_kw"]) - float(original_grid_kw)
    elif active_mode == "energy_target":
        raw_power_kw = (float(schedule_values["energy_target_kwh"]) - float(current_energy_kwh)) / HALF_HOUR_HOURS
    else:
        raw_power_kw = 0.0
    battery_kw = clip_battery_power_by_limits(
        raw_power_kw=raw_power_kw,
        power_limit_kw=battery_params.battery_power_limit_kw,
        current_energy_kwh=current_energy_kwh,
        capacity_kwh=battery_params.battery_capacity_kwh,
    )
    return battery_kw, active_mode
