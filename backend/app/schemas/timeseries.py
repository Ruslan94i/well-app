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
    water_cut_algorithm: float | None = None
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
    qliq_wfm: float | None = None
    qliq_vfm: float | None = None
