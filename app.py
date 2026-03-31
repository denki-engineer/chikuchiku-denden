"""ちくちくでんでん Streamlit エントリーポイント。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

try:
    from chikuchiku_denden.calculators import calculate_step2, calculate_step3
    from chikuchiku_denden.io_utils import load_default_project
    from chikuchiku_denden.models import ProjectData, SimulationResult, Step2Result, Step3Result
    from chikuchiku_denden.ui_components import (
        render_project_io,
        render_step1,
        render_step2,
        render_step3,
        render_step4,
        render_step5,
        render_step6,
        render_top_summary,
    )
except ModuleNotFoundError:  # app.py ?????????????????
    from calculators import calculate_step2, calculate_step3
    from io_utils import load_default_project
    from models import ProjectData, SimulationResult, Step2Result, Step3Result
    from ui_components import (
        render_project_io,
        render_step1,
        render_step2,
        render_step3,
        render_step4,
        render_step5,
        render_step6,
        render_top_summary,
    )

DEFAULTS_DIR = Path(__file__).resolve().parent / "defaults"
STEP_NAMES = ["STEP1", "STEP2", "STEP3", "STEP4", "STEP5", "STEP6"]
DEFAULT_STEP3_TARGET_KW = 350.0


def _step2_signature(project: ProjectData) -> tuple:
    return (
        project.updated_at,
        project.planA.basic_rate_yen_per_kw_month,
        tuple(project.planA.holiday_list),
        project.planB.basic_rate_yen_per_kw_month,
        tuple(project.planB.holiday_list),
        len(project.energy_df),
    )


def _step3_signature(project: ProjectData, target_grid_kw: float) -> tuple:
    return (
        project.updated_at,
        float(target_grid_kw),
        len(project.step3_profile_df),
    )


def _initial_project() -> ProjectData:
    """初期プロジェクトを返す。"""

    return load_default_project(str(DEFAULTS_DIR)).validate()


def initialize_session_state() -> None:
    """初回起動時のセッション状態を初期化する。"""

    if "project" not in st.session_state:
        st.session_state.project = _initial_project()
    if "step3_target_grid_kw" not in st.session_state:
        st.session_state.step3_target_grid_kw = DEFAULT_STEP3_TARGET_KW
    if "step2_result" not in st.session_state:
        st.session_state.step2_result = None
    if "step3_result" not in st.session_state:
        st.session_state.step3_result = None
    if "simulation_result" not in st.session_state:
        st.session_state.simulation_result = None
    if "active_step" not in st.session_state:
        st.session_state.active_step = "STEP1"
    if "step2_signature" not in st.session_state:
        st.session_state.step2_signature = None
    if "step3_signature" not in st.session_state:
        st.session_state.step3_signature = None



def main() -> None:
    """アプリ本体を描画する。"""

    st.set_page_config(page_title="ちくちくでんでん", layout="wide")
    initialize_session_state()

    project: ProjectData = st.session_state.project
    simulation_result: SimulationResult | None = st.session_state.simulation_result

    project = render_project_io(project, simulation_result)
    st.session_state.project = project

    step2_signature = _step2_signature(project)
    if st.session_state.step2_signature != step2_signature:
        try:
            st.session_state.step2_result = calculate_step2(project.energy_df, project.planA, project.planB)
        except Exception:
            st.session_state.step2_result = None
        st.session_state.step2_signature = step2_signature

    step3_signature = _step3_signature(project, float(st.session_state.step3_target_grid_kw))
    if st.session_state.step3_signature != step3_signature:
        try:
            st.session_state.step3_result = calculate_step3(float(st.session_state.step3_target_grid_kw), project.step3_profile_df)
        except Exception:
            st.session_state.step3_result = None
        st.session_state.step3_signature = step3_signature

    step2_result: Step2Result | None = st.session_state.step2_result
    step3_result: Step3Result | None = st.session_state.step3_result

    st.title("ちくちくでんでん")
    st.caption("料金プラン比較・蓄電池導入効果の概算評価アプリ")
    render_top_summary(step2_result, step3_result)

    st.radio("表示するSTEP", STEP_NAMES, key="active_step", horizontal=True)

    if st.session_state.active_step == "STEP1":
        st.session_state.project = render_step1(project)
    elif st.session_state.active_step == "STEP2":
        st.session_state.project, st.session_state.step2_result = render_step2(project)
    elif st.session_state.active_step == "STEP3":
        st.session_state.project, st.session_state.step3_result = render_step3(project)
    elif st.session_state.active_step == "STEP4":
        st.session_state.project = render_step4(project)
    elif st.session_state.active_step == "STEP5":
        st.session_state.project, st.session_state.simulation_result = render_step5(project)
    elif st.session_state.active_step == "STEP6":
        render_step6(project, st.session_state.simulation_result)


if __name__ == "__main__":
    main()
