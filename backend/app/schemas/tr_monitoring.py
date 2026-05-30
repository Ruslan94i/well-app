from datetime import date

from pydantic import BaseModel


class TrMonitoringPoint(BaseModel):
    date: date
    reservoir_pressure: float | None = None
    dynamic_level: float | None = None
    intake_pressure: float | None = None
    bottomhole_pressure: float | None = None
    oil_rate: float | None = None
    liquid_rate: float | None = None
    water_cut: float | None = None
    pump_pressure: float | None = None
    gas_factor: float | None = None
    productivity: float | None = None
