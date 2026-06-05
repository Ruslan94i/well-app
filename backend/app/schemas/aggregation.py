from pydantic import BaseModel, Field


class AggregateRequest(BaseModel):
    frequency_threshold: int = Field(default=5, description="Change threshold for ESP frequency: 5 or 10.")
    telemetry_threshold: int = Field(default=10, description="Change threshold for other telemetry parameters: 5 or 10.")


class UpdateRequest(BaseModel):
    source_folder: str
    frequency_threshold: int = Field(default=5, description="Change threshold for ESP frequency: 5 or 10.")
    telemetry_threshold: int = Field(default=10, description="Change threshold for other telemetry parameters: 5 or 10.")


class AggregationStartResponse(BaseModel):
    status: str


class AggregationStatusResponse(BaseModel):
    status: str
    wells_done: int
    wells_total: int
    message: str | None = None
