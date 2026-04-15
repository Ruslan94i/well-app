from datetime import date

from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: date
    qliq: float | None = None
    qoil: float | None = None
    qgas: float | None = None
    gas_factor: float | None = None
    gas_liquid_factor: float | None = None
    qliq_wfm: float | None = None
    qliq_vfm: float | None = None
    water_cut: float | None = None
    intake_pressure: float | None = None
    esp_frequency: float | None = None
    load: float | None = None
