from pydantic import BaseModel


class FundControlWellFactorRow(BaseModel):
    well_id: str
    field_code: str
    vqliq_start: float | None = None
    vqliq_end: float | None = None
    total_delta: float | None = None
    stop_rate: float | None = None
    stop_gdi: float = 0.0
    frequency: float = 0.0
    periodic: float = 0.0
    complicated: float = 0.0
    water_supply: float = 0.0
    nur: float = 0.0
    kprod: float = 0.0
    reservoir_pressure: float = 0.0
    gas_factor: float = 0.0
    calibration_tr: float = 0.0
    background: float = 0.0
    balance_error: float = 0.0


class FundControlFactorSummaryRow(BaseModel):
    factor: str
    total: float
    sum_loss: float
    sum_gain: float
    top5_down: str
    top5_up: str
    action_loss: str | None = None
    action_gain: str | None = None


class FundControlResponse(BaseModel):
    period_start: str
    period_end: str
    rows: list[FundControlWellFactorRow]
    factors: list[FundControlFactorSummaryRow]
    max_abs_balance_error: float
    balance_check_passed: bool
