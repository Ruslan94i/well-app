from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: str
    qliq: float | None = None
    predicted_qliq: float | None = None
    buffer_pressure: float | None = None
    casing_pressure: float | None = None
    load: float | None = None
    water_cut: float | None = None
    water_cut_hal: float | None = None
    water_cut_hal_density: float | None = None
    water_cut_hal_daily: float | None = None
    water_cut_algo: float | None = None
    water_cut_mode: str | None = None
    intake_pressure: float | None = None
    esp_frequency: float | None = None
    active_power: float | None = None
    bdpv_volume_rate: float | None = None
    bdpv_water_flow: float | None = None
    collector_pressure: float | None = None
    full_power: float | None = None
    qgas: float | None = None
    qoil: float | None = None
    gas_factor: float | None = None
    gas_liquid_factor: float | None = None
    free_gas_pct: float | None = None
    qliq_wfm: float | None = None
    qliq_vfm: float | None = None
    ozna_session_id: str | None = None
    ozna_duration_min: float | None = None
    ozna_n_points: int | None = None
    ozna_quality_flags: str | None = None
    ozna_source_files: str | None = None
    ozna_qliq: float | None = None
    ozna_qliq_p10: float | None = None
    ozna_qliq_p90: float | None = None
    ozna_qliq_cv_pct: float | None = None
    ozna_qoil: float | None = None
    ozna_qoil_p10: float | None = None
    ozna_qoil_p90: float | None = None
    ozna_qoil_cv_pct: float | None = None
    ozna_qgas: float | None = None
    ozna_qgas_p10: float | None = None
    ozna_qgas_p90: float | None = None
    ozna_qgas_cv_pct: float | None = None
