"""STEP3 calculation engine."""

from __future__ import annotations

import pandas as pd

try:
    from chikuchiku_denden.models import Step3Result
except ModuleNotFoundError:
    from models import Step3Result


def calculate_step3(target_grid_kw: float, profile_df: pd.DataFrame) -> Step3Result:
    """Calculate required battery power and energy for the reference profile."""

    df = profile_df.copy()
    df["load_kw"] = pd.to_numeric(df["load_kw"], errors="raise")
    df["pv_kw"] = pd.to_numeric(df["pv_kw"], errors="raise")
    df["p_battery_kw"] = float(target_grid_kw) - df["load_kw"] - df["pv_kw"]
    return Step3Result(
        required_power_kw=float(df["p_battery_kw"].max()),
        required_energy_kwh=float(df["p_battery_kw"].clip(lower=0).sum()),
        result_df=df,
    )
