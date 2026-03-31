"""内部データモデル定義。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


def _require_non_negative(name: str, value: float) -> float:
    numeric_value = float(value)
    if numeric_value < 0:
        raise ValueError(f"{name} は 0 以上である必要があります。")
    return numeric_value


def _require_columns(name: str, df: pd.DataFrame, required_columns: Iterable[str]) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{name} に不足列があります: {missing}")


@dataclass
class TariffPlan:
    """料金プラン設定。"""

    name: str
    basic_rate_yen_per_kw_month: float
    holiday_list: list[str]
    tariff_df: pd.DataFrame

    def validate(self) -> "TariffPlan":
        if not self.name.strip():
            raise ValueError("料金プラン名は空にできません。")
        _require_non_negative("基本料金単価[円/kW・月]", self.basic_rate_yen_per_kw_month)
        _require_columns("tariff_df", self.tariff_df, ("month", "day_type", "time_slot", "unit_price"))
        return self


@dataclass
class Step2Result:
    """STEP2の導入前料金計算結果。"""

    annual_energy_kwh: float
    annual_max_grid_kw_before: float
    planA_basic_cost_before: float
    planA_energy_cost_before: float
    planA_total_cost_before: float
    planB_basic_cost_before: float
    planB_energy_cost_before: float
    planB_total_cost_before: float


@dataclass
class BatteryParams:
    """蓄電池パラメータ。"""

    battery_power_limit_kw: float
    battery_capacity_kwh: float
    battery_initial_energy_kwh: float

    def validate(self) -> "BatteryParams":
        _require_non_negative("充放電能力[kW]", self.battery_power_limit_kw)
        _require_non_negative("充電容量[kWh]", self.battery_capacity_kwh)
        _require_non_negative("初期充電量[kWh]", self.battery_initial_energy_kwh)
        if self.battery_initial_energy_kwh > self.battery_capacity_kwh:
            raise ValueError("初期充電量[kWh] は充電容量[kWh] 以下である必要があります。")
        return self


@dataclass
class Step3ProfilePoint:
    """STEP3の1時点分プロファイル。"""

    time_label: str
    load_kw: float
    pv_kw: float


@dataclass
class Step3Result:
    """STEP3の参考計算結果。"""

    required_power_kw: float
    required_energy_kwh: float
    result_df: pd.DataFrame


@dataclass
class SimulationResult:
    """STEP5/STEP6のシミュレーション結果。"""

    timeseries_df: pd.DataFrame
    monthly_summary_df: pd.DataFrame
    annual_summary_df: pd.DataFrame
    representative_week_df: pd.DataFrame


@dataclass
class ProjectData:
    """プロジェクト全体の永続化対象。"""

    project_name: str
    created_at: str
    updated_at: str
    planA: TariffPlan
    planB: TariffPlan
    target_year: int
    energy_df: pd.DataFrame
    step3_profile_df: pd.DataFrame
    operation_holiday_list: list[str]
    battery_params: BatteryParams
    battery_schedule_df: pd.DataFrame

    def validate(self) -> "ProjectData":
        self.planA.validate()
        self.planB.validate()
        self.battery_params.validate()
        _require_columns("energy_df", self.energy_df, ("date", "time", "kWh"))
        _require_columns("step3_profile_df", self.step3_profile_df, ("time", "load_kw", "pv_kw"))
        if "time_slot" not in self.battery_schedule_df.columns:
            raise ValueError("battery_schedule_df に time_slot 列が必要です。")
        return self
