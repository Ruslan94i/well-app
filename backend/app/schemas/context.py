from pydantic import BaseModel, Field


class GtmEvent(BaseModel):
    id: str
    wellId: str
    startDate: str
    endDate: str
    operationType: str
    direction: str | None = None
    durationDays: int | None = None
    oilBefore: float | None = None
    liquidBefore: float | None = None
    waterCutBefore: float | None = None
    oilAfter: float | None = None
    liquidAfter: float | None = None
    waterCutAfter: float | None = None
    comment: str = ""


class OpzEvent(BaseModel):
    id: str
    wellId: str
    date: str
    operationType: str
    category: str | None = None
    composition: str | None = None
    volume: float | None = None
    capexOpex: str | None = None
    result: str | None = None
    deltaOil: float | None = None
    comment: str = ""


class GdiEvent(BaseModel):
    id: str
    wellId: str
    startDate: str
    endDate: str
    operationType: str
    acceptedVdpPressure: int | None = None
    productivityVogel: float | None = None
    quality: int | None = None
    executor: str | None = None
    durationHours: float | None = None
    comment: str = ""


class WellContext(BaseModel):
    wellId: str
    gtm: list[GtmEvent] = Field(default_factory=list)
    opz: list[OpzEvent] = Field(default_factory=list)
    gdi: list[GdiEvent] = Field(default_factory=list)
