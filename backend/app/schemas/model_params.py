from pydantic import BaseModel, ConfigDict


class ModelParamValue(BaseModel):
    value: float


class ModelParamOverrides(BaseModel):
    model_config = ConfigDict(extra="ignore")

    params: dict[str, float]


class ModelParamsState(BaseModel):
    globalParams: dict[str, float]
    overrides: dict[str, dict[str, float]]
