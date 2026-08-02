from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REFERENCE_DIR = _PROJECT_ROOT / "backend" / "data" / "reference"

# High-resolution telemetry source used for re-aggregation / VFM rebuild.
# Defaults to bundled reference data and can be overridden via TELEMETRY_DATA_PATH.
_TELEMETRY_DATA_DEFAULT = _REFERENCE_DIR


class Settings(BaseSettings):
    app_name: str = "Анализ скважинной динамики API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    csv_data_path: Path = _PROJECT_ROOT / "well_metrics_v9.csv"
    telemetry_data_path: Path = _TELEMETRY_DATA_DEFAULT
    aggregated_telemetry_data_path: Path = _TELEMETRY_DATA_DEFAULT / "aggregated"
    telemetry_aggregated_data_path: Path = aggregated_telemetry_data_path / "telemetry.csv"
    telemetry_10_data_path: Path = aggregated_telemetry_data_path / "telemetry_10.csv"
    measurements_data_path: Path = aggregated_telemetry_data_path / "measurements.csv"
    power_daily_data_path: Path = aggregated_telemetry_data_path / "power_daily.csv"
    markup_data_path: Path = Path(__file__).resolve().parents[3] / "backend" / "data" / "markup.json"
    reference_data_path: Path = Path(__file__).resolve().parents[3] / "backend" / "data" / "reference"
    tr_monitoring_data_path: Path = reference_data_path / "tr_monitoring.csv"
    auto_episode_segments_data_path: Path = reference_data_path / "auto_episode_segments.csv"
    water_cut_hal_data_path: Path = reference_data_path / "water_cut_hal.csv"
    water_cut_algorithm_data_path: Path = reference_data_path / "full_inference_water_cut.csv"
    predicted_qliq_data_path: Path = reference_data_path / "predicted_qliq.csv"
    predicted_qliq_meta_path: Path = reference_data_path / "predicted_qliq_meta.json"
    ozna_source_data_path: Path = reference_data_path / "ozna_source.csv"
    ozna_raw_data_path: Path = reference_data_path / "ozna_measurements_raw.csv"
    ozna_sessions_data_path: Path = reference_data_path / "ozna_sessions.csv"
    ozna_pvt_density_data_path: Path = reference_data_path / "pvt_density_by_prefix.csv"
    ozna_oil_density_check_data_path: Path = reference_data_path / "ozna_oil_density_check.csv"
    ozna_session_gap_minutes: int = 60
    ozna_short_session_minutes: int = 30
    ozna_few_points_min: int = 30
    ozna_unstable_cv_pct: float = 100.0
    ozna_drifting_pct: float = 30.0
    ozna_gas_line_gap_days: float = 1.0
    well_params_data_path: Path = reference_data_path / "well_params.json"
    episodes_table_data_path: Path = reference_data_path / "episodes.csv"
    episodes_compute_script_path: Path = Path(__file__).resolve().parents[3] / "exports" / "episode_rules_v13_5.py"
    episodes_compute_telemetry_data_path: Path = reference_data_path / "well_graph_data_all_full_enriched.csv"
    episodes_compute_pvt_data_path: Path = reference_data_path / "pvtcharacteristics_20260525_111417.xlsx"
    episodes_compute_enriched_data_path: Path = reference_data_path / "well_graph_data_all_full_enriched.csv"
    episodes_compute_kprod_data_path: Path = reference_data_path / "kprod_algorithm.csv"
    episodes_scheduler_enabled: bool = False
    episodes_scheduler_hour_utc: int = 2
    episodes_compute_timeout_seconds: int = 21600
    episodes_model_version: str = "episode_rules_v13_5"
    artificial_lift_data_path: Path = reference_data_path / "artificial_lift.xlsx"
    intra_shift_downtime_data_path: Path = reference_data_path / "intra_shift_downtime_20260521_105050.xlsx"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
