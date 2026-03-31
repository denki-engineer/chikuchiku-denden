"""STEP2 calculation engine."""

from __future__ import annotations

try:
    from chikuchiku_denden.engine.calendar_engine import ensure_energy_columns
    from chikuchiku_denden.engine.tariff_engine import attach_tariff_prices
    from chikuchiku_denden.models import Step2Result, TariffPlan
except ModuleNotFoundError:
    from engine.calendar_engine import ensure_energy_columns
    from engine.tariff_engine import attach_tariff_prices
    from models import Step2Result, TariffPlan


def calculate_step2(energy_df, planA: TariffPlan, planB: TariffPlan) -> Step2Result:
    """Calculate annual pre-install costs."""

    planA.validate()
    planB.validate()
    df = ensure_energy_columns(energy_df)
    df = attach_tariff_prices(df, planA, "planA")
    df = attach_tariff_prices(df, planB, "planB")
    annual_energy_kwh = float(df["kWh"].sum())
    annual_max_grid_kw_before = float(df["original_grid_kw_30min_avg"].max())
    planA_basic_cost_before = annual_max_grid_kw_before * planA.basic_rate_yen_per_kw_month * 12
    planB_basic_cost_before = annual_max_grid_kw_before * planB.basic_rate_yen_per_kw_month * 12
    planA_energy_cost_before = float((df["kWh"] * df["planA_unit_price"]).sum())
    planB_energy_cost_before = float((df["kWh"] * df["planB_unit_price"]).sum())
    return Step2Result(
        annual_energy_kwh=annual_energy_kwh,
        annual_max_grid_kw_before=annual_max_grid_kw_before,
        planA_basic_cost_before=planA_basic_cost_before,
        planA_energy_cost_before=planA_energy_cost_before,
        planA_total_cost_before=planA_basic_cost_before + planA_energy_cost_before,
        planB_basic_cost_before=planB_basic_cost_before,
        planB_energy_cost_before=planB_energy_cost_before,
        planB_total_cost_before=planB_basic_cost_before + planB_energy_cost_before,
    )
