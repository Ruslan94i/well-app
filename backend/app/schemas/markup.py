from typing import Literal

from pydantic import BaseModel, Field


class AnnotationClassOption(BaseModel):
    label: str
    value: str


class FrequencyBreakpoint(BaseModel):
    id: str
    wellId: str
    date: str
    source: Literal["auto", "manual"]
    reason: str = ""
    fromFrequency: float | None = None
    toFrequency: float | None = None


class FrequencyBreakpointSuppression(BaseModel):
    id: str
    wellId: str
    date: str


class AnnotationBase(BaseModel):
    id: str
    wellId: str
    wellGroupId: str | None = None
    startDate: str
    endDate: str
    durationDays: int
    comment: str = ""
    actions: list[str] = Field(default_factory=list)


class SavedEventAnnotation(AnnotationBase):
    annotationKind: Literal["event"]
    eventType: str
    confidenceEvent: Literal["low", "medium", "high"]


class SavedRootCauseAnnotation(AnnotationBase):
    annotationKind: Literal["rootCause"]
    rootCause: str
    confidenceCause: Literal["low", "medium", "high"]


SavedAnnotation = SavedEventAnnotation | SavedRootCauseAnnotation


class MarkupState(BaseModel):
    annotations: list[SavedAnnotation] = Field(default_factory=list)
    episodeClasses: list[AnnotationClassOption] = Field(default_factory=list)
    modeClasses: list[AnnotationClassOption] = Field(default_factory=list)
    actionClasses: list[AnnotationClassOption] = Field(default_factory=list)
    manualFrequencyBreakpoints: list[FrequencyBreakpoint] = Field(default_factory=list)
    suppressedFrequencyBreakpoints: list[FrequencyBreakpointSuppression] = Field(default_factory=list)
