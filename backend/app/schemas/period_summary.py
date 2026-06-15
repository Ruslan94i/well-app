from pydantic import BaseModel


class PeriodSummaryRow(BaseModel):
    field_code: str
    well_id: str
    category: str
    interval_start: str
    interval_end: str
    duration_days: float | None = None
    stop_qliq: float | None = None
    qliq_1: float | None = None
    qliq_2: float | None = None
    qoil_1: float | None = None
    qoil_2: float | None = None
    water_cut_1: float | None = None
    water_cut_2: float | None = None
    intake_pressure_1: float | None = None
    intake_pressure_2: float | None = None
    frequency_1: float | None = None
    frequency_2: float | None = None
    load_1: float | None = None
    load_2: float | None = None
    gas_factor_1: float | None = None
    gas_factor_2: float | None = None
    bdpv_1: float | None = None
    bdpv_2: float | None = None
    delta_qliq: float | None = None
    delta_qoil: float | None = None
    accumulated_qliq: float | None = None
    accumulated_qoil: float | None = None


class PeriodSummaryResponse(BaseModel):
    period_start: str
    period_end: str
    window_days: float
    rows: list[PeriodSummaryRow]
