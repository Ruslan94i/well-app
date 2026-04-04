from datetime import date

from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: date
    qliq: float
    qoil: float
    qliq_vfm: float
    water_cut: float
    intake_pressure: float
    esp_frequency: float
    load: float

