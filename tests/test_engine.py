from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from chikuchiku_denden.engine.battery_engine import select_representative_week, simulate_battery
from chikuchiku_denden.engine.calendar_engine import build_operation_calendar
from chikuchiku_denden.engine.tariff_engine import attach_tariff_prices
from chikuchiku_denden.models import BatteryParams, TariffPlan
from chikuchiku_denden.ui_components import _simulate_battery_cached

TIME_SLOTS = [
    f"{hour:02d}:{minute:02d}-" + ("24:00" if hour == 23 and minute == 30 else f"{(hour + (1 if minute == 30 else 0)):02d}:{(minute + 30) % 60:02d}")
    for hour in range(24)
    for minute in (0, 30)
]


def build_tariff_df(weekday_price: float = 10.0, holiday_price: float = 20.0) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in range(1, 13):
        for day_type, price in (("weekday", weekday_price), ("holiday", holiday_price)):
            for slot in TIME_SLOTS:
                rows.append(
                    {
                        "month": month,
                        "day_type": day_type,
                        "time_slot": slot,
                        "unit_price": price,
                    }
                )
    return pd.DataFrame(rows)


def build_schedule_df() -> pd.DataFrame:
    data: dict[str, object] = {"time_slot": TIME_SLOTS}
    for month in range(1, 13):
        for day_label in ("稼働日", "休業日"):
            for mode_name in ("固定(kW)", "GRID目標(kW)", "容量目標(kWh)"):
                data[f"{month}月_{day_label}_{mode_name}"] = [np.nan] * len(TIME_SLOTS)
    return pd.DataFrame(data)


def build_energy_df(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", "time", "kWh"])


def build_plan(name: str = "プラン", weekday_price: float = 10.0, holiday_price: float = 20.0) -> TariffPlan:
    return TariffPlan(
        name=name,
        basic_rate_yen_per_kw_month=1000.0,
        holiday_list=[],
        tariff_df=build_tariff_df(weekday_price=weekday_price, holiday_price=holiday_price),
    )


class BatteryEngineTests(unittest.TestCase):
    def test_fixed_mode_charge_and_discharge_are_clipped(self) -> None:
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_稼働日_固定(kW)"] = 30.0
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])
        result_charge = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(20.0, 5.0, 0.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result_charge.timeseries_df.iloc[0]["battery_kw"], 10.0)
        self.assertAlmostEqual(result_charge.timeseries_df.iloc[0]["battery_energy_kwh"], 5.0)

        schedule_df.loc[0, "1月_稼働日_固定(kW)"] = -30.0
        result_discharge = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(20.0, 100.0, 5.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result_discharge.timeseries_df.iloc[0]["battery_kw"], -10.0)
        self.assertAlmostEqual(result_discharge.timeseries_df.iloc[0]["battery_energy_kwh"], 0.0)

    def test_grid_target_mode_respects_power_and_energy_limits(self) -> None:
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_稼働日_GRID目標(kW)"] = 50.0
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])

        result_power = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(20.0, 100.0, 100.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result_power.timeseries_df.iloc[0]["battery_kw"], -20.0)

        result_energy = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(20.0, 100.0, 5.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result_energy.timeseries_df.iloc[0]["battery_kw"], -10.0)
        self.assertAlmostEqual(result_energy.timeseries_df.iloc[0]["battery_energy_kwh"], 0.0)

    def test_energy_target_mode_hits_requested_end_energy(self) -> None:
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_稼働日_容量目標(kWh)"] = 10.0
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])
        result = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(50.0, 100.0, 0.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_kw"], 20.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_energy_kwh"], 10.0)

    def test_saturday_is_weekday_for_tariff_and_holiday_for_operation(self) -> None:
        energy_df = build_energy_df([("2025-01-04", "00:00", 10.0)])  # Saturday
        operation_df = build_operation_calendar(energy_df, [])
        tariff_df = attach_tariff_prices(energy_df, build_plan("A", weekday_price=11.0, holiday_price=22.0), "planA")
        self.assertEqual(operation_df.iloc[0]["operation_day_type"], "holiday")
        self.assertEqual(tariff_df.iloc[0]["planA_tariff_day_type"], "weekday")
        self.assertAlmostEqual(tariff_df.iloc[0]["planA_unit_price"], 11.0)

    def test_initial_energy_is_applied_only_once_at_year_start(self) -> None:
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_稼働日_固定(kW)"] = -20.0
        schedule_df.loc[1, "1月_稼働日_固定(kW)"] = 0.0
        energy_df = build_energy_df(
            [
                ("2025-01-01", "00:00", 50.0),
                ("2025-01-01", "00:30", 50.0),
            ]
        )
        result = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(20.0, 100.0, 10.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_energy_kwh"], 0.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[1]["battery_energy_kwh"], 0.0)

    def test_all_modes_blank_results_in_zero_kw(self) -> None:
        schedule_df = build_schedule_df()
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])
        result = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(50.0, 100.0, 10.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_kw"], 0.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_energy_kwh"], 10.0)

    def test_discharge_request_is_clipped_to_zero_when_soc_is_zero(self) -> None:
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_稼働日_固定(kW)"] = -30.0
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])
        result = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(50.0, 100.0, 0.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_kw"], 0.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_energy_kwh"], 0.0)

    def test_charge_request_is_clipped_to_zero_when_capacity_is_full(self) -> None:
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_稼働日_固定(kW)"] = 30.0
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])
        result = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(50.0, 100.0, 100.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_kw"], 0.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_energy_kwh"], 100.0)

    def test_soc_is_continuous_across_month_boundaries_and_until_year_end(self) -> None:
        schedule_df = build_schedule_df()
        for day_label in ("稼働日", "休業日"):
            schedule_df.loc[TIME_SLOTS.index("23:30-24:00"), f"1月_{day_label}_固定(kW)"] = -20.0
            schedule_df.loc[TIME_SLOTS.index("00:00-00:30"), f"2月_{day_label}_固定(kW)"] = 0.0
            schedule_df.loc[TIME_SLOTS.index("23:00-23:30"), f"12月_{day_label}_固定(kW)"] = 0.0
            schedule_df.loc[TIME_SLOTS.index("23:30-24:00"), f"12月_{day_label}_固定(kW)"] = 0.0
        energy_df = build_energy_df(
            [
                ("2025-01-31", "23:30", 50.0),
                ("2025-02-01", "00:00", 50.0),
                ("2025-12-31", "23:00", 50.0),
                ("2025-12-31", "23:30", 50.0),
            ]
        )
        result = simulate_battery(
            energy_df=energy_df,
            battery_params=BatteryParams(20.0, 100.0, 20.0),
            battery_schedule_df=schedule_df,
            operation_holiday_list=[],
            planA=build_plan("A"),
            planB=build_plan("B"),
        )
        self.assertAlmostEqual(result.timeseries_df.iloc[0]["battery_energy_kwh"], 10.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[1]["battery_energy_kwh"], 10.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[2]["battery_energy_kwh"], 10.0)
        self.assertAlmostEqual(result.timeseries_df.iloc[3]["battery_energy_kwh"], 10.0)

    def test_representative_week_tie_break_prefers_earlier_week(self) -> None:
        timeseries_df = pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2025-01-06 00:00", "2025-01-13 00:00"]),
                "original_grid_kw_30min_avg": [100.0, 100.0],
                "battery_kw": [20.0, -20.0],
            }
        )
        representative = select_representative_week(timeseries_df)
        self.assertEqual(representative.iloc[0]["datetime"], pd.Timestamp("2025-01-06 00:00:00"))


class StreamlitCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        _simulate_battery_cached.clear()

    def test_step5_cache_recomputes_when_inputs_change(self) -> None:
        energy_df = build_energy_df([("2025-01-01", "00:00", 50.0)])
        schedule_df = build_schedule_df()
        schedule_df.loc[0, "1月_休業日_固定(kW)"] = 0.0
        planA = build_plan("A")
        planB = build_plan("B")

        result_zero = _simulate_battery_cached(
            energy_df=energy_df,
            battery_power_limit_kw=20.0,
            battery_capacity_kwh=100.0,
            battery_initial_energy_kwh=0.0,
            battery_schedule_df=schedule_df,
            operation_holiday_list=tuple(),
            planA_name=planA.name,
            planA_basic_rate_yen_per_kw_month=planA.basic_rate_yen_per_kw_month,
            planA_holiday_list=tuple(planA.holiday_list),
            planA_tariff_df=planA.tariff_df,
            planB_name=planB.name,
            planB_basic_rate_yen_per_kw_month=planB.basic_rate_yen_per_kw_month,
            planB_holiday_list=tuple(planB.holiday_list),
            planB_tariff_df=planB.tariff_df,
        )
        result_ten = _simulate_battery_cached(
            energy_df=energy_df,
            battery_power_limit_kw=20.0,
            battery_capacity_kwh=100.0,
            battery_initial_energy_kwh=10.0,
            battery_schedule_df=schedule_df,
            operation_holiday_list=tuple(),
            planA_name=planA.name,
            planA_basic_rate_yen_per_kw_month=planA.basic_rate_yen_per_kw_month,
            planA_holiday_list=tuple(planA.holiday_list),
            planA_tariff_df=planA.tariff_df,
            planB_name=planB.name,
            planB_basic_rate_yen_per_kw_month=planB.basic_rate_yen_per_kw_month,
            planB_holiday_list=tuple(planB.holiday_list),
            planB_tariff_df=planB.tariff_df,
        )
        result_zero_again = _simulate_battery_cached(
            energy_df=energy_df,
            battery_power_limit_kw=20.0,
            battery_capacity_kwh=100.0,
            battery_initial_energy_kwh=0.0,
            battery_schedule_df=schedule_df,
            operation_holiday_list=tuple(),
            planA_name=planA.name,
            planA_basic_rate_yen_per_kw_month=planA.basic_rate_yen_per_kw_month,
            planA_holiday_list=tuple(planA.holiday_list),
            planA_tariff_df=planA.tariff_df,
            planB_name=planB.name,
            planB_basic_rate_yen_per_kw_month=planB.basic_rate_yen_per_kw_month,
            planB_holiday_list=tuple(planB.holiday_list),
            planB_tariff_df=planB.tariff_df,
        )

        self.assertAlmostEqual(result_zero.timeseries_df.iloc[0]["battery_energy_kwh"], 0.0)
        self.assertAlmostEqual(result_ten.timeseries_df.iloc[0]["battery_energy_kwh"], 10.0)
        self.assertAlmostEqual(result_zero_again.timeseries_df.iloc[0]["battery_energy_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
