from pydantic import BaseModel


class ArtificialLiftPeriod(BaseModel):
    id: str
    wellId: str
    espId: str
    startDate: str
    endDate: str | None = None
    failureDate: str | None = None
    liftReason: str | None = None
    espSize: str | None = None
    nominalRate: float | None = None
    gasSeparatorType: str | None = None
    motorPowerKw: float | None = None
    isFountain: bool = False
