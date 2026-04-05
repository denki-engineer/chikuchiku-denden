"""Streamlit UI コンポーネント。"""

from __future__ import annotations

import tempfile
from numbers import Real
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

try:
    from chikuchiku_denden.calculators import (
        build_step6_assumption_text,
        calculate_step2,
        calculate_step3,
        parse_holiday_text,
        simulate_battery,
    )
    from chikuchiku_denden.io_utils import (
        export_project_zip_bytes,
        import_project_zip_from_bytes,
        load_battery_schedule_csv,
        load_energy_csv,
        load_step3_profile_csv,
        load_tariff_csv,
        update_project_timestamp,
    )
    from chikuchiku_denden.models import BatteryParams, ProjectData, SimulationResult, Step2Result, Step3Result, TariffPlan
except ModuleNotFoundError:  # app.py ?????????????????
    from calculators import (
        build_step6_assumption_text,
        calculate_step2,
        calculate_step3,
        parse_holiday_text,
        simulate_battery,
    )
    from io_utils import (
        export_project_zip_bytes,
        import_project_zip_from_bytes,
        load_battery_schedule_csv,
        load_energy_csv,
        load_step3_profile_csv,
        load_tariff_csv,
        update_project_timestamp,
    )
    from models import BatteryParams, ProjectData, SimulationResult, Step2Result, Step3Result, TariffPlan


DEFAULT_STEP3_TARGET_KW = 350.0


def _configure_matplotlib_font() -> None:
    available_fonts = {font.name for font in fm.fontManager.ttflist}
    for font_name in ("Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic", "Noto Sans CJK JP"):
        if font_name in available_fonts:
            plt.rcParams["font.family"] = [font_name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _format_number(value: object) -> object:
    if pd.isna(value) or isinstance(value, bool) or not isinstance(value, Real):
        return value
    formatted = f"{float(value):,.3f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _format_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    for column in display_df.columns:
        display_df[column] = display_df[column].map(_format_number)
    return display_df


@st.cache_data(show_spinner=False)
def _simulate_battery_cached(
    energy_df: pd.DataFrame,
    battery_power_limit_kw: float,
    battery_capacity_kwh: float,
    battery_initial_energy_kwh: float,
    battery_schedule_df: pd.DataFrame,
    operation_holiday_list: tuple[str, ...],
    planA_name: str,
    planA_basic_rate_yen_per_kw_month: float,
    planA_holiday_list: tuple[str, ...],
    planA_tariff_df: pd.DataFrame,
    planB_name: str,
    planB_basic_rate_yen_per_kw_month: float,
    planB_holiday_list: tuple[str, ...],
    planB_tariff_df: pd.DataFrame,
) -> SimulationResult:
    """Cache STEP5 results by explicit immutable inputs to avoid stale reuse."""

    return simulate_battery(
        energy_df=energy_df,
        battery_params=BatteryParams(
            battery_power_limit_kw=battery_power_limit_kw,
            battery_capacity_kwh=battery_capacity_kwh,
            battery_initial_energy_kwh=battery_initial_energy_kwh,
        ),
        battery_schedule_df=battery_schedule_df,
        operation_holiday_list=list(operation_holiday_list),
        planA=TariffPlan(
            name=planA_name,
            basic_rate_yen_per_kw_month=planA_basic_rate_yen_per_kw_month,
            holiday_list=list(planA_holiday_list),
            tariff_df=planA_tariff_df,
        ),
        planB=TariffPlan(
            name=planB_name,
            basic_rate_yen_per_kw_month=planB_basic_rate_yen_per_kw_month,
            holiday_list=list(planB_holiday_list),
            tariff_df=planB_tariff_df,
        ),
    )


def _sync_step5_battery_state(project: ProjectData) -> None:
    """Keep STEP5 battery inputs stable across Streamlit reruns."""

    state_signature = (
        project.updated_at,
        float(project.battery_params.battery_power_limit_kw),
        float(project.battery_params.battery_capacity_kwh),
        float(project.battery_params.battery_initial_energy_kwh),
    )
    has_widget_state = all(
        key in st.session_state
        for key in (
            "step5_battery_power_limit_kw",
            "step5_battery_capacity_kwh",
            "step5_battery_initial_energy_kwh",
        )
    )
    if st.session_state.get("step5_battery_signature") != state_signature or not has_widget_state:
        st.session_state.step5_battery_power_limit_kw = float(project.battery_params.battery_power_limit_kw)
        st.session_state.step5_battery_capacity_kwh = float(project.battery_params.battery_capacity_kwh)
        st.session_state.step5_battery_initial_energy_kwh = float(project.battery_params.battery_initial_energy_kwh)
        st.session_state.step5_battery_signature = state_signature


def _sync_step1_plan_state(project: ProjectData, plan_key: str) -> None:
    plan: TariffPlan = getattr(project, plan_key)
    signature = (
        project.updated_at,
        float(plan.basic_rate_yen_per_kw_month),
        tuple(plan.holiday_list),
    )
    state_key = f"{plan_key}_input_signature"
    has_widget_state = all(
        key in st.session_state
        for key in (
            f"{plan_key}_basic_rate_input",
            f"{plan_key}_holiday_text",
        )
    )
    if st.session_state.get(state_key) != signature or not has_widget_state:
        st.session_state[f"{plan_key}_basic_rate_input"] = float(plan.basic_rate_yen_per_kw_month)
        st.session_state[f"{plan_key}_holiday_text"] = _textarea_holidays(plan.holiday_list)
        st.session_state[state_key] = signature


def _sync_step2_state(project: ProjectData) -> None:
    signature = (project.updated_at, int(project.target_year))
    if st.session_state.get("step2_target_year_signature") != signature:
        st.session_state.step2_target_year = int(project.target_year)
        st.session_state.step2_target_year_signature = signature


def _sync_step4_state(project: ProjectData) -> None:
    signature = (project.updated_at, tuple(project.operation_holiday_list))
    if st.session_state.get("step4_operation_holiday_signature") != signature:
        st.session_state.step4_operation_holiday_text = _textarea_holidays(project.operation_holiday_list)
        st.session_state.step4_operation_holiday_signature = signature


def _textarea_holidays(values: list[str]) -> str:
    return "\n".join(values)


def _save_uploaded_file(uploaded_file, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


def _download_csv_button(label: str, df: pd.DataFrame, file_name: str) -> None:
    st.download_button(label=label, data=df.to_csv(index=False, encoding="utf-8-sig"), file_name=file_name, mime="text/csv")


def render_top_summary(step2_result: Step2Result | None, step3_result: Step3Result | None) -> None:
    """トップ画面の要約を表示する。"""

    cols = st.columns(4)
    cols[0].metric("プランA 電気料金合計_導入前", "-" if step2_result is None else f"{step2_result.planA_total_cost_before:,.0f} 円")
    cols[1].metric("プランB 電気料金合計_導入前", "-" if step2_result is None else f"{step2_result.planB_total_cost_before:,.0f} 円")
    cols[2].metric("STEP3 充放電能力", "-" if step3_result is None else f"{step3_result.required_power_kw:,.1f} kW")
    cols[3].metric("STEP3 充電容量", "-" if step3_result is None else f"{step3_result.required_energy_kwh:,.1f} kWh")


def render_step1(project: ProjectData) -> ProjectData:
    """STEP1 UI を描画し、ProjectDataへ反映する。"""

    st.subheader("STEP1: 電力量単価を入力する")
    for plan_key in ("planA", "planB"):
        plan: TariffPlan = getattr(project, plan_key)
        _sync_step1_plan_state(project, plan_key)
        st.markdown(f"#### {plan.name}")
        left, right = st.columns([1, 1.5])
        basic_rate = left.number_input(
            f"{plan.name} 基本料金単価 [円/kW・月]",
            min_value=0.0,
            step=10.0,
            key=f"{plan_key}_basic_rate_input",
        )
        holiday_text = right.text_area(
            f"{plan.name} 追加休日一覧",
            height=140,
            key=f"{plan_key}_holiday_text",
        )
        upload = st.file_uploader(f"{plan.name} 従量単価CSV", type=["csv"], key=f"{plan_key}_tariff_upload")
        _download_csv_button(f"{plan.name} 従量単価CSVをダウンロード", plan.tariff_df, f"{plan_key}_tariff.csv")
        if st.button(f"{plan.name} 設定を反映", key=f"{plan_key}_apply"):
            plan.basic_rate_yen_per_kw_month = float(basic_rate)
            plan.holiday_list = parse_holiday_text(holiday_text)
            if upload is not None:
                upload_path = _save_uploaded_file(upload, ".csv")
                plan.tariff_df = load_tariff_csv(upload_path)
            update_project_timestamp(project)
            st.session_state[f"{plan_key}_input_signature"] = (
                project.updated_at,
                float(plan.basic_rate_yen_per_kw_month),
                tuple(plan.holiday_list),
            )
            st.success(f"{plan.name} の設定を更新しました。")
    return project


def render_step2(project: ProjectData) -> tuple[ProjectData, Step2Result | None]:
    """STEP2 UI を描画し結果を返す。"""

    st.subheader("STEP2: 電力量を入力する")
    project.target_year = int(st.number_input("対象年", min_value=2000, max_value=2100, value=int(project.target_year), step=1))
    upload = st.file_uploader("年間30分電力量CSV", type=["csv"], key="energy_upload")
    if upload is not None and st.button("電力量CSVを読み込む"):
        upload_path = _save_uploaded_file(upload, ".csv")
        project.energy_df = load_energy_csv(upload_path)
        source_year = project.energy_df.attrs.get("source_year")
        source_months = project.energy_df.attrs.get("source_months", [])
        if source_year is not None:
            project.target_year = int(source_year)
        update_project_timestamp(project)
        if source_year is not None and source_months:
            month_text = ", ".join(f"{int(month)}月" for month in source_months)
            st.success(f"電力量CSVを更新しました。読込期間: {int(source_year)}年 {month_text}")
        else:
            st.success("電力量CSVを更新しました。")

    step2_result: Step2Result | None = None
    try:
        step2_result = calculate_step2(project.energy_df, project.planA, project.planB)
    except Exception as exc:  # noqa: BLE001
        st.error(f"STEP2計算に失敗しました: {exc}")

    if step2_result is not None:
        step2_display_df = _format_dataframe_for_display(
            pd.DataFrame(
                [
                    {"項目": "年間電力量", "値": step2_result.annual_energy_kwh, "単位": "kWh"},
                    {"項目": "年間最大需要電力", "値": step2_result.annual_max_grid_kw_before, "単位": "kW"},
                    {"項目": "プランA 年間基本料金_導入前", "値": step2_result.planA_basic_cost_before, "単位": "円"},
                    {"項目": "プランA 年間従量料金_導入前", "値": step2_result.planA_energy_cost_before, "単位": "円"},
                    {"項目": "プランA 年間電気料金合計_導入前", "値": step2_result.planA_total_cost_before, "単位": "円"},
                    {"項目": "プランB 年間基本料金_導入前", "値": step2_result.planB_basic_cost_before, "単位": "円"},
                    {"項目": "プランB 年間従量料金_導入前", "値": step2_result.planB_energy_cost_before, "単位": "円"},
                    {"項目": "プランB 年間電気料金合計_導入前", "値": step2_result.planB_total_cost_before, "単位": "円"},
                ]
            )
        )
        st.dataframe(
            step2_display_df,
            use_container_width=True,
            hide_index=True,
        )
    _download_csv_button("電力量CSVをダウンロード", project.energy_df[["date", "time", "kWh"]], "energy_2025.csv")
    return project, step2_result


def render_step3(project: ProjectData) -> tuple[ProjectData, Step3Result | None]:
    """STEP3 UI を描画し結果を返す。"""

    st.subheader("STEP3: 太陽光余剰電力吸収の参考計算")
    target_grid_kw = st.number_input("目標受電電力[kW]", min_value=0.0, value=float(st.session_state.get("step3_target_grid_kw", DEFAULT_STEP3_TARGET_KW)), step=10.0)
    st.session_state.step3_target_grid_kw = target_grid_kw
    upload = st.file_uploader("STEP3プロファイルCSV", type=["csv"], key="step3_profile_upload")
    if upload is not None and st.button("STEP3プロファイルCSVを読み込む"):
        upload_path = _save_uploaded_file(upload, ".csv")
        project.step3_profile_df = load_step3_profile_csv(upload_path)
        update_project_timestamp(project)
        st.success("STEP3プロファイルを更新しました。")
    edited_df = st.data_editor(project.step3_profile_df, use_container_width=True, num_rows="fixed", key="step3_profile_editor")
    if st.button("STEP3表を反映"):
        project.step3_profile_df = pd.DataFrame(edited_df)
        update_project_timestamp(project)
        st.success("STEP3表を更新しました。")
    step3_result: Step3Result | None = None
    try:
        step3_result = calculate_step3(target_grid_kw, project.step3_profile_df)
        st.metric("必要充放電能力", f"{step3_result.required_power_kw:,.1f} kW")
        st.metric("必要充電容量", f"{step3_result.required_energy_kwh:,.1f} kWh")
    except Exception as exc:  # noqa: BLE001
        st.error(f"STEP3計算に失敗しました: {exc}")
    return project, step3_result


def render_step4(project: ProjectData) -> ProjectData:
    """STEP4 UI を描画し、休業日設定を反映する。"""

    st.subheader("STEP4: 工場のスケジュールを入力する")
    st.info("法定祝日は自動判定しません。土曜日は単価判定では平日、蓄電池スケジュールでは休業日です。")
    holiday_text = st.text_area("追加休業日一覧", value=_textarea_holidays(project.operation_holiday_list), height=220)
    if st.button("STEP4設定を反映"):
        project.operation_holiday_list = parse_holiday_text(holiday_text)
        update_project_timestamp(project)
        st.success("追加休業日を更新しました。")
    st.caption("優先順: 追加休業日 > 日曜日 > 土曜日 > 平日")
    return project


def render_step5(project: ProjectData) -> tuple[ProjectData, SimulationResult | None]:
    """STEP5 UI を描画し、シミュレーション結果を返す。"""

    st.subheader("STEP5: 蓄電池設定と月毎効果確認")
    _sync_step5_battery_state(project)

    original_params = (
        float(project.battery_params.battery_power_limit_kw),
        float(project.battery_params.battery_capacity_kwh),
        float(project.battery_params.battery_initial_energy_kwh),
    )
    upper_cols = st.columns(3)
    battery_power_limit_kw = float(
        upper_cols[0].number_input(
            "充放電能力[kW]",
            min_value=0.0,
            step=50.0,
            key="step5_battery_power_limit_kw",
        )
    )
    battery_capacity_kwh = float(
        upper_cols[1].number_input(
            "充電容量[kWh]",
            min_value=0.0,
            step=100.0,
            key="step5_battery_capacity_kwh",
        )
    )
    battery_initial_energy_kwh = float(
        upper_cols[2].number_input(
            "初期充電量[kWh]",
            min_value=0.0,
            step=100.0,
            key="step5_battery_initial_energy_kwh",
        )
    )

    project.battery_params.battery_power_limit_kw = battery_power_limit_kw
    project.battery_params.battery_capacity_kwh = battery_capacity_kwh
    project.battery_params.battery_initial_energy_kwh = battery_initial_energy_kwh
    updated_params = (
        battery_power_limit_kw,
        battery_capacity_kwh,
        battery_initial_energy_kwh,
    )
    if updated_params != original_params:
        update_project_timestamp(project)
        st.session_state.step5_battery_signature = (
            project.updated_at,
            battery_power_limit_kw,
            battery_capacity_kwh,
            battery_initial_energy_kwh,
        )

    control_cols = st.columns(3)
    month = int(control_cols[0].selectbox("編集する月", options=list(range(1, 13)), index=0))
    day_label = control_cols[1].selectbox("編集する日種別", options=["稼働日", "休業日"])
    schedule_upload = control_cols[2].file_uploader("スケジュールCSV", type=["csv"], key="schedule_upload")

    if schedule_upload is not None and st.button("スケジュールCSVを読み込む"):
        upload_path = _save_uploaded_file(schedule_upload, ".csv")
        project.battery_schedule_df = load_battery_schedule_csv(upload_path)
        update_project_timestamp(project)
        st.success("スケジュールCSVを更新しました。")

    edit_columns = [
        "time_slot",
        f"{month}月_{day_label}_固定(kW)",
        f"{month}月_{day_label}_GRID目標(kW)",
        f"{month}月_{day_label}_容量目標(kWh)",
    ]
    edited_schedule = st.data_editor(project.battery_schedule_df[edit_columns], use_container_width=True, num_rows="fixed", key=f"schedule_editor_{month}_{day_label}")
    if st.button("STEP5編集内容を反映"):
        project.battery_schedule_df.loc[:, edit_columns] = pd.DataFrame(edited_schedule)[edit_columns]
        update_project_timestamp(project)
        st.success("STEP5編集内容を反映しました。")
    _download_csv_button("スケジュールCSVをダウンロード", project.battery_schedule_df, "battery_schedule.csv")

    simulation_result: SimulationResult | None = None
    try:
        simulation_result = _simulate_battery_cached(
            energy_df=project.energy_df,
            battery_power_limit_kw=project.battery_params.battery_power_limit_kw,
            battery_capacity_kwh=project.battery_params.battery_capacity_kwh,
            battery_initial_energy_kwh=project.battery_params.battery_initial_energy_kwh,
            battery_schedule_df=project.battery_schedule_df,
            operation_holiday_list=tuple(project.operation_holiday_list),
            planA_name=project.planA.name,
            planA_basic_rate_yen_per_kw_month=project.planA.basic_rate_yen_per_kw_month,
            planA_holiday_list=tuple(project.planA.holiday_list),
            planA_tariff_df=project.planA.tariff_df,
            planB_name=project.planB.name,
            planB_basic_rate_yen_per_kw_month=project.planB.basic_rate_yen_per_kw_month,
            planB_holiday_list=tuple(project.planB.holiday_list),
            planB_tariff_df=project.planB.tariff_df,
        )
        monthly_view = simulation_result.monthly_summary_df.rename(columns={
            "month": "month",
            "max_grid_kw_before": "GRID最大値_導入前[kW]",
            "max_grid_kw_after": "GRID最大値_導入後[kW]",
            "delta_max_grid_kw": "GRID最大値_差分[kW]",
            "planA_energy_cost_before": "プランA 従量料金_導入前[円]",
            "planA_energy_cost_after": "プランA 従量料金_導入後[円]",
            "delta_planA_energy_cost": "プランA 従量料金_差分[円]",
            "planB_energy_cost_before": "プランB 従量料金_導入前[円]",
            "planB_energy_cost_after": "プランB 従量料金_導入後[円]",
            "delta_planB_energy_cost": "プランB 従量料金_差分[円]",
        })
        st.dataframe(_format_dataframe_for_display(monthly_view), use_container_width=True, hide_index=True)
        _download_csv_button("STEP5計算結果CSVをダウンロード", simulation_result.timeseries_df, "simulation_result.csv")

        _configure_matplotlib_font()
        fig, ax = plt.subplots(figsize=(12, 4))
        rep = simulation_result.representative_week_df
        ax.plot(rep["datetime"], rep["original_grid_kw_30min_avg"], label="導入前GRID")
        ax.plot(rep["datetime"], rep["adjusted_grid_kw_30min_avg"], label="導入後GRID")
        ax.plot(rep["datetime"], rep["battery_kw"], label="蓄電池電力")
        ax.set_ylabel("30分平均電力[kW]")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.autofmt_xdate()
        st.pyplot(fig)
        plt.close(fig)
    except Exception as exc:  # noqa: BLE001
        st.error(f"STEP5計算に失敗しました: {exc}")
    return project, simulation_result


def render_step6(project: ProjectData, simulation_result: SimulationResult | None) -> None:
    """STEP6 UI を描画する。"""

    st.subheader("STEP6: 年間料金確認")
    if simulation_result is None:
        st.info("先にSTEP5を実行してください。")
        return
    annual_df = simulation_result.annual_summary_df.copy()
    display_df = pd.DataFrame(
        [
            {"プラン": "プランA", "項目": "年間基本料金", "導入前[円]": annual_df.iloc[0]["planA_basic_cost_before"], "導入後[円]": annual_df.iloc[0]["planA_basic_cost_after"], "差分[円]": annual_df.iloc[0]["planA_basic_cost_after"] - annual_df.iloc[0]["planA_basic_cost_before"]},
            {"プラン": "プランA", "項目": "年間従量料金", "導入前[円]": annual_df.iloc[0]["planA_energy_cost_before"], "導入後[円]": annual_df.iloc[0]["planA_energy_cost_after"], "差分[円]": annual_df.iloc[0]["planA_energy_cost_after"] - annual_df.iloc[0]["planA_energy_cost_before"]},
            {"プラン": "プランA", "項目": "年間電気料金合計", "導入前[円]": annual_df.iloc[0]["planA_total_cost_before"], "導入後[円]": annual_df.iloc[0]["planA_total_cost_after"], "差分[円]": annual_df.iloc[0]["delta_planA_total_cost"]},
            {"プラン": "プランB", "項目": "年間基本料金", "導入前[円]": annual_df.iloc[0]["planB_basic_cost_before"], "導入後[円]": annual_df.iloc[0]["planB_basic_cost_after"], "差分[円]": annual_df.iloc[0]["planB_basic_cost_after"] - annual_df.iloc[0]["planB_basic_cost_before"]},
            {"プラン": "プランB", "項目": "年間従量料金", "導入前[円]": annual_df.iloc[0]["planB_energy_cost_before"], "導入後[円]": annual_df.iloc[0]["planB_energy_cost_after"], "差分[円]": annual_df.iloc[0]["planB_energy_cost_after"] - annual_df.iloc[0]["planB_energy_cost_before"]},
            {"プラン": "プランB", "項目": "年間電気料金合計", "導入前[円]": annual_df.iloc[0]["planB_total_cost_before"], "導入後[円]": annual_df.iloc[0]["planB_total_cost_after"], "差分[円]": annual_df.iloc[0]["delta_planB_total_cost"]},
        ]
    )
    st.dataframe(_format_dataframe_for_display(display_df), use_container_width=True, hide_index=True)
    st.text(build_step6_assumption_text())


def render_project_io(project: ProjectData, simulation_result: SimulationResult | None) -> ProjectData:
    """プロジェクトZIPの入出力UI。"""

    st.sidebar.header("プロジェクト")
    uploaded_zip = st.sidebar.file_uploader("プロジェクトZIPを読み込む", type=["zip"])
    if uploaded_zip is not None and st.sidebar.button("ZIPをインポート"):
        project = import_project_zip_from_bytes(uploaded_zip.getvalue())
        st.sidebar.success("プロジェクトZIPを読み込みました。")
    zip_bytes = export_project_zip_bytes(project, None if simulation_result is None else simulation_result.timeseries_df)
    st.sidebar.download_button("プロジェクトZIPをエクスポート", data=zip_bytes, file_name="chikuchiku_denden_project.zip", mime="application/zip")
    return project
