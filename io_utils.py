"""CSV / JSON / ZIP の入出力処理。"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
from dataclasses import asdict
from datetime import datetime
import time
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from chikuchiku_denden.engine.calendar_engine import TIME_SLOTS
    from chikuchiku_denden.models import BatteryParams, ProjectData, TariffPlan
except ModuleNotFoundError:  # app.py ?????????????????
    from engine.calendar_engine import TIME_SLOTS
    from models import BatteryParams, ProjectData, TariffPlan

SCHEDULE_DAY_LABELS = ("稼働日", "休業日")
SCHEDULE_MODES = ("固定(kW)", "GRID目標(kW)", "容量目標(kWh)")


def _read_csv_with_fallback(path: str, **kwargs) -> pd.DataFrame:
    """Read CSV using utf-8-sig first, then cp932 as a fallback."""

    for encoding in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _normalize_time_slot(value: str) -> str:
    start_text, end_text = str(value).strip().split("-")
    start_hour, start_minute = [int(part) for part in start_text.split(":")]
    end_hour, end_minute = [int(part) for part in end_text.split(":")]
    start = f"{start_hour:02d}:{start_minute:02d}"
    end = "24:00" if end_hour == 24 and end_minute == 0 else f"{end_hour:02d}:{end_minute:02d}"
    return f"{start}-{end}"


def _validate_tariff_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ["month", "day_type", "time_slot", "unit_price"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"tariff CSV に不足列があります: {missing}")
    df = df[required].copy()
    df["month"] = pd.to_numeric(df["month"], errors="raise").astype(int)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="raise")
    df["time_slot"] = df["time_slot"].map(_normalize_time_slot)
    if not df["month"].between(1, 12).all():
        raise ValueError("month は 1～12 である必要があります。")
    if not df["day_type"].isin(["weekday", "holiday"]).all():
        raise ValueError("day_type は weekday / holiday のみ対応です。")
    if len(df) != 1152:
        raise ValueError("tariff CSV は 1152 行を想定しています。")
    expected = {(month, day_type, slot) for month in range(1, 13) for day_type in ("weekday", "holiday") for slot in TIME_SLOTS}
    actual = set(zip(df["month"], df["day_type"], df["time_slot"]))
    if expected != actual:
        raise ValueError("tariff CSV の month/day_type/time_slot の組み合わせが不正です。")
    return df.sort_values(["month", "day_type", "time_slot"]).reset_index(drop=True)


def _convert_wide_tariff_csv(df: pd.DataFrame) -> pd.DataFrame:
    normalized_columns = [unicodedata.normalize("NFKC", str(column)).strip() for column in df.columns]
    df = df.copy()
    df.columns = normalized_columns
    time_slot_column = normalized_columns[0]
    records: list[dict[str, object]] = []
    pattern = re.compile(r"^(\d{1,2})月(平日|休日)$")

    for _, row in df.iterrows():
        time_slot = _normalize_time_slot(row[time_slot_column])
        for column in normalized_columns[1:]:
            match = pattern.match(column)
            if match is None:
                continue
            month = int(match.group(1))
            day_type = "weekday" if match.group(2) == "平日" else "holiday"
            records.append(
                {
                    "month": month,
                    "day_type": day_type,
                    "time_slot": time_slot,
                    "unit_price": row[column],
                }
            )

    return pd.DataFrame.from_records(records)


def _validate_energy_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ["date", "time", "kWh"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"電力量CSVに不足列があります: {missing}")
    df = df[required].copy()
    df["kWh"] = pd.to_numeric(df["kWh"], errors="raise")
    df["time"] = df["time"].astype(str).str.slice(0, 5)
    df["datetime"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"], errors="raise")
    df = df.sort_values("datetime").reset_index(drop=True)
    if df["datetime"].duplicated().any():
        duplicated = df.loc[df["datetime"].duplicated(), "datetime"].iloc[0]
        raise ValueError(f"電力量CSVに重複日時があります: {duplicated}")
    expected_range = pd.date_range(df["datetime"].min(), df["datetime"].max(), freq="30min")
    missing_range = expected_range.difference(pd.Index(df["datetime"]))
    if len(missing_range) > 0:
        raise ValueError(f"電力量CSVに欠損日時があります。最初の欠損は {missing_range[0]} です。")
    df["original_grid_kw_30min_avg"] = df["kWh"] * 2
    df.attrs["source_year"] = int(df["datetime"].dt.year.mode().iloc[0])
    df.attrs["source_months"] = sorted(df["datetime"].dt.month.unique().tolist())
    return df


def _convert_monthly_energy_report(raw_df: pd.DataFrame) -> pd.DataFrame:
    title_cell = unicodedata.normalize("NFKC", str(raw_df.iat[0, 0])).strip()
    match = re.search(r"(\d{4})年(\d{1,2})月分", title_cell)
    if match is None:
        raise ValueError("電力使用量CSVの先頭から 年/月 を読み取れませんでした。")
    year = int(match.group(1))
    month = int(match.group(2))

    header_row = raw_df.iloc[2].map(lambda value: unicodedata.normalize("NFKC", str(value)).strip())
    day_columns: list[tuple[int, int]] = []
    for column_index in range(2, len(header_row)):
        header_value = header_row.iloc[column_index]
        if header_value.startswith("合計"):
            break
        day_match = re.match(r"(\d{1,2})日", header_value)
        if day_match is None:
            continue
        day_columns.append((column_index, int(day_match.group(1))))

    records: list[dict[str, object]] = []
    for row_index in range(3, len(raw_df)):
        time_slot_raw = unicodedata.normalize("NFKC", str(raw_df.iat[row_index, 1])).strip()
        if "-" not in time_slot_raw:
            continue
        time_slot = _normalize_time_slot(time_slot_raw)
        start_time = time_slot.split("-")[0]
        for column_index, day in day_columns:
            value = raw_df.iat[row_index, column_index]
            if pd.isna(value) or str(value).strip() == "":
                continue
            records.append(
                {
                    "date": f"{year:04d}-{month:02d}-{day:02d}",
                    "time": start_time,
                    "kWh": value,
                }
            )

    if not records:
        raise ValueError("電力使用量CSVから30分データを抽出できませんでした。")

    df = pd.DataFrame.from_records(records)
    df.attrs["source_year"] = year
    df.attrs["source_months"] = [month]
    return df


def load_tariff_csv(path: str) -> pd.DataFrame:
    """tariff CSV を読み込みバリデーションする。"""

    df = _read_csv_with_fallback(path)
    if {"month", "day_type", "time_slot", "unit_price"}.issubset(df.columns):
        return _validate_tariff_df(df)
    return _validate_tariff_df(_convert_wide_tariff_csv(df))


def save_tariff_csv(df: pd.DataFrame, path: str) -> None:
    """tariff CSV を保存する。"""

    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_energy_csv(path: str) -> pd.DataFrame:
    """電力量CSVを読み込み、時系列検証を行う。"""

    df = _read_csv_with_fallback(path)
    if {"date", "time", "kWh"}.issubset(df.columns):
        return _validate_energy_df(df)
    raw_df = _read_csv_with_fallback(path, header=None)
    converted_df = _convert_monthly_energy_report(raw_df)
    return _validate_energy_df(converted_df)


def save_energy_csv(df: pd.DataFrame, path: str) -> None:
    """電力量CSVを保存する。"""

    df[["date", "time", "kWh"]].to_csv(path, index=False, encoding="utf-8-sig")


def load_step3_profile_csv(path: str) -> pd.DataFrame:
    """STEP3プロファイルCSVを読み込む。"""

    df = pd.read_csv(path, encoding="utf-8-sig")
    required = ["time", "load_kw", "pv_kw"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"STEP3プロファイルCSVに不足列があります: {missing}")
    df = df[required].copy()
    df["load_kw"] = pd.to_numeric(df["load_kw"], errors="raise")
    df["pv_kw"] = pd.to_numeric(df["pv_kw"], errors="raise")
    return df


def save_step3_profile_csv(df: pd.DataFrame, path: str) -> None:
    """STEP3プロファイルCSVを保存する。"""

    df[["time", "load_kw", "pv_kw"]].to_csv(path, index=False, encoding="utf-8-sig")


def load_battery_schedule_csv(path: str) -> pd.DataFrame:
    """STEP5用スケジュールCSVを厳密に読み込む。"""

    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [unicodedata.normalize("NFKC", str(column)) for column in df.columns]
    if df.columns[0].startswith("Unnamed") or df.columns[0] == "":
        df = df.rename(columns={df.columns[0]: "time_slot"})
    if df.columns[0] != "time_slot":
        raise ValueError("スケジュールCSVの1列目は time_slot である必要があります。")
    df["time_slot"] = df["time_slot"].map(_normalize_time_slot)
    if list(df["time_slot"]) != TIME_SLOTS:
        raise ValueError("スケジュールCSVの time_slot は 48 個の30分枠である必要があります。")
    expected_columns = ["time_slot"]
    for month in range(1, 13):
        for day_label in SCHEDULE_DAY_LABELS:
            for mode in SCHEDULE_MODES:
                expected_columns.append(f"{month}月_{day_label}_{mode}")
    missing = [column for column in expected_columns if column not in df.columns]
    if missing:
        raise ValueError(f"スケジュールCSVに不足列があります: {missing[:5]}")
    return df[expected_columns].copy()


def save_battery_schedule_csv(df: pd.DataFrame, path: str) -> None:
    """STEP5用スケジュールCSVを保存する。"""

    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_project_json(path: str) -> dict[str, Any]:
    """project.json を読み込む。"""

    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_project_json(data: dict[str, Any], path: str) -> None:
    """project.json を保存する。"""

    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _project_to_dict(project: ProjectData) -> dict[str, Any]:
    """ProjectData を JSON 保存向け dict に変換する。"""

    return {
        "project_name": project.project_name,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "target_year": project.target_year,
        "planA": {
            "name": project.planA.name,
            "basic_rate_yen_per_kw_month": project.planA.basic_rate_yen_per_kw_month,
            "holiday_list": project.planA.holiday_list,
        },
        "planB": {
            "name": project.planB.name,
            "basic_rate_yen_per_kw_month": project.planB.basic_rate_yen_per_kw_month,
            "holiday_list": project.planB.holiday_list,
        },
        "operation_holiday_list": project.operation_holiday_list,
        "battery_params": asdict(project.battery_params),
    }


def export_project_zip(project: ProjectData, output_zip_path: str, optional_result_df: pd.DataFrame | None = None) -> None:
    """ProjectData を ZIP 形式で保存する。"""

    with zipfile.ZipFile(output_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(_project_to_dict(project), ensure_ascii=False, indent=2))
        zf.writestr("planA_tariff.csv", project.planA.tariff_df.to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("planB_tariff.csv", project.planB.tariff_df.to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("energy_2025.csv", project.energy_df[["date", "time", "kWh"]].to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("battery_schedule.csv", project.battery_schedule_df.to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("step3_profile.csv", project.step3_profile_df[["time", "load_kw", "pv_kw"]].to_csv(index=False, encoding="utf-8-sig"))
        if optional_result_df is not None:
            zf.writestr("simulation_result.csv", optional_result_df.to_csv(index=False, encoding="utf-8-sig"))


def import_project_zip(zip_path: str) -> ProjectData:
    """ZIP を展開せずに ProjectData を復元する。"""

    required_files = {
        "project.json",
        "planA_tariff.csv",
        "planB_tariff.csv",
        "energy_2025.csv",
        "battery_schedule.csv",
        "step3_profile.csv",
    }
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        missing = required_files.difference(names)
        if missing:
            raise ValueError(f"ZIP に必須ファイルが不足しています: {sorted(missing)}")
        meta = json.loads(zf.read("project.json").decode("utf-8-sig"))
        planA_tariff_df = pd.read_csv(io.BytesIO(zf.read("planA_tariff.csv")), encoding="utf-8-sig")
        planB_tariff_df = pd.read_csv(io.BytesIO(zf.read("planB_tariff.csv")), encoding="utf-8-sig")
        energy_df = pd.read_csv(io.BytesIO(zf.read("energy_2025.csv")), encoding="utf-8-sig")
        schedule_df = pd.read_csv(io.BytesIO(zf.read("battery_schedule.csv")), encoding="utf-8-sig")
        step3_df = pd.read_csv(io.BytesIO(zf.read("step3_profile.csv")), encoding="utf-8-sig")
    return ProjectData(
        project_name=meta["project_name"],
        created_at=meta["created_at"],
        updated_at=meta["updated_at"],
        planA=TariffPlan(
            name=meta["planA"]["name"],
            basic_rate_yen_per_kw_month=float(meta["planA"]["basic_rate_yen_per_kw_month"]),
            holiday_list=list(meta["planA"]["holiday_list"]),
            # TODO: load_* の検証ロジック再利用のため一時CSVを経由している。将来的にはメモリ上で検証したい。
            tariff_df=load_tariff_csv(_save_dataframe_temp(planA_tariff_df)),
        ),
        planB=TariffPlan(
            name=meta["planB"]["name"],
            basic_rate_yen_per_kw_month=float(meta["planB"]["basic_rate_yen_per_kw_month"]),
            holiday_list=list(meta["planB"]["holiday_list"]),
            # TODO: load_* の検証ロジック再利用のため一時CSVを経由している。将来的にはメモリ上で検証したい。
            tariff_df=load_tariff_csv(_save_dataframe_temp(planB_tariff_df)),
        ),
        target_year=int(meta["target_year"]),
        # TODO: load_* の検証ロジック再利用のため一時CSVを経由している。将来的にはメモリ上で検証したい。
        energy_df=load_energy_csv(_save_dataframe_temp(energy_df)),
        # TODO: load_* の検証ロジック再利用のため一時CSVを経由している。将来的にはメモリ上で検証したい。
        step3_profile_df=load_step3_profile_csv(_save_dataframe_temp(step3_df)),
        operation_holiday_list=list(meta["operation_holiday_list"]),
        battery_params=BatteryParams(**meta["battery_params"]),
        # TODO: load_* の検証ロジック再利用のため一時CSVを経由している。将来的にはメモリ上で検証したい。
        battery_schedule_df=load_battery_schedule_csv(_save_dataframe_temp(schedule_df)),
    ).validate()


def _save_dataframe_temp(df: pd.DataFrame) -> str:
    """検証関数再利用のため、ワークスペース内の一時CSVへ保存する。

    TODO: ZIP import は現在ここを経由して load_* の既存検証を再利用している。
    将来的には BytesIO / DataFrame ベースの検証関数へ寄せて一時CSVをなくしたい。
    """

    temp_dir = Path(".codex_tmp")
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"tmp_{time.time_ns()}.csv"
    df.to_csv(temp_path, index=False, encoding="utf-8-sig")
    return str(temp_path)


def load_default_project(defaults_dir: str) -> ProjectData:
    """defaults フォルダから初期 ProjectData を生成する。"""

    base_dir = Path(defaults_dir)
    meta = load_project_json(str(base_dir / "default_project.json"))
    return ProjectData(
        project_name=meta["project_name"],
        created_at=meta["created_at"],
        updated_at=meta["updated_at"],
        planA=TariffPlan(
            name=meta["planA"]["name"],
            basic_rate_yen_per_kw_month=float(meta["planA"]["basic_rate_yen_per_kw_month"]),
            holiday_list=list(meta["planA"]["holiday_list"]),
            tariff_df=load_tariff_csv(str(base_dir / "planA_tariff.csv")),
        ),
        planB=TariffPlan(
            name=meta["planB"]["name"],
            basic_rate_yen_per_kw_month=float(meta["planB"]["basic_rate_yen_per_kw_month"]),
            holiday_list=list(meta["planB"]["holiday_list"]),
            tariff_df=load_tariff_csv(str(base_dir / "planB_tariff.csv")),
        ),
        target_year=int(meta["target_year"]),
        energy_df=load_energy_csv(str(base_dir / "energy_2025.csv")),
        step3_profile_df=load_step3_profile_csv(str(base_dir / "step3_profile.csv")),
        operation_holiday_list=list(meta["operation_holiday_list"]),
        battery_params=BatteryParams(**meta["battery_params"]),
        battery_schedule_df=load_battery_schedule_csv(str(base_dir / "battery_schedule.csv")),
    ).validate()


def export_project_zip_bytes(project: ProjectData, optional_result_df: pd.DataFrame | None = None) -> bytes:
    """Streamlit ダウンロード向けに ZIP バイト列を返す。"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(_project_to_dict(project), ensure_ascii=False, indent=2))
        zf.writestr("planA_tariff.csv", project.planA.tariff_df.to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("planB_tariff.csv", project.planB.tariff_df.to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("energy_2025.csv", project.energy_df[["date", "time", "kWh"]].to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("battery_schedule.csv", project.battery_schedule_df.to_csv(index=False, encoding="utf-8-sig"))
        zf.writestr("step3_profile.csv", project.step3_profile_df[["time", "load_kw", "pv_kw"]].to_csv(index=False, encoding="utf-8-sig"))
        if optional_result_df is not None:
            zf.writestr("simulation_result.csv", optional_result_df.to_csv(index=False, encoding="utf-8-sig"))
    return buffer.getvalue()


def import_project_zip_from_bytes(data: bytes) -> ProjectData:
    """Streamlit アップロード向けに ZIP バイト列から復元する。"""

    temp_dir = Path(".codex_tmp")
    temp_dir.mkdir(exist_ok=True)
    zip_path = temp_dir / f"upload_{time.time_ns()}.zip"
    zip_path.write_bytes(data)
    return import_project_zip(str(zip_path))


def update_project_timestamp(project: ProjectData) -> ProjectData:
    """updated_at を現在時刻へ更新する。"""

    project.updated_at = datetime.now().isoformat(timespec="seconds")
    return project
