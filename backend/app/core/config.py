from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Анализ скважинной динамики API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]
    csv_data_path: Path = Path(__file__).resolve().parents[3] / "well_metrics_v9.csv"
    telemetry_data_path: Path = Path(r"D:\1 Ирито\5 WellInsight\telemetry")
    aggregated_telemetry_data_path: Path = telemetry_data_path / "aggregated"
    telemetry_aggregated_data_path: Path = aggregated_telemetry_data_path / "telemetry.csv"
    telemetry_10_data_path: Path = aggregated_telemetry_data_path / "telemetry_10.csv"
    measurements_data_path: Path = aggregated_telemetry_data_path / "measurements.csv"
    power_daily_data_path: Path = aggregated_telemetry_data_path / "power_daily.csv"
    markup_data_path: Path = Path(__file__).resolve().parents[3] / "backend" / "data" / "markup.json"
    reference_data_path: Path = Path(__file__).resolve().parents[3] / "backend" / "data" / "reference"
    tr_monitoring_data_path: Path = reference_data_path / "tr_monitoring.csv"
    auto_episode_segments_data_path: Path = reference_data_path / "auto_episode_segments.csv"
    water_cut_hal_data_path: Path = reference_data_path / "water_cut_hal.csv"
    predicted_qliq_data_path: Path = reference_data_path / "predicted_qliq.csv"
    water_cut_algorithm_model_path: Path = reference_data_path / "water_cut_algorithm_model.joblib"
    well_params_data_path: Path = reference_data_path / "well_params.json"
    episodes_table_data_path: Path = reference_data_path / "episodes.csv"
    episodes_compute_script_path: Path = Path(__file__).resolve().parents[3] / "exports" / "episode_rules_v10_2.py"
    episodes_compute_telemetry_data_path: Path = reference_data_path / "well_graph_data_all_full.csv"
    episodes_compute_wct_data_path: Path = reference_data_path / "full_inference_water_cut.csv"
    episodes_compute_enriched_data_path: Path = reference_data_path / "well_graph_data_all_full_enriched.csv"
    episodes_compute_kprod_data_path: Path = reference_data_path / "kprod_algorithm.csv"
    episodes_scheduler_enabled: bool = False
    episodes_scheduler_hour_utc: int = 2
    episodes_compute_timeout_seconds: int = 21600
    episodes_model_version: str = "episode_rules_v10_2"
    artificial_lift_data_path: Path = reference_data_path / "artificial_lift.xlsx"
    intra_shift_downtime_data_path: Path = reference_data_path / "intra_shift_downtime_20260521_105050.xlsx"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
