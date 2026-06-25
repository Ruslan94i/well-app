from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelParamValue(BaseModel):
    value: float


class ModelParamOverrides(BaseModel):
    model_config = ConfigDict(extra="ignore")

    params: dict[str, float]


class ModelParamsState(BaseModel):
    globalParams: dict[str, float]
    overrides: dict[str, dict[str, float]]


class AutomarkRecomputeScope(BaseModel):
    type: Literal["well", "field", "set"]
    field: str | None = None
    well: str | None = None
    preview_well: str | None = None
    wells: list[str] = Field(default_factory=list)


class AutomarkRecomputeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scope: AutomarkRecomputeScope
    overrides: dict[str, float] = Field(default_factory=dict)


class AutomarkQualityRow(BaseModel):
    field: str
    wells: int
    rows: str
    pct: float
    note: str


class AutomarkRecomputeResponse(BaseModel):
    overall_before: float
    overall_after: float
    by_category_before: dict[str, float]
    by_category_after: dict[str, float]
    rows: list[AutomarkQualityRow]
    preview_intervals: list[dict[str, Any]] = Field(default_factory=list)
