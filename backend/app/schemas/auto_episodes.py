from pydantic import BaseModel


class AutoEpisodeInterval(BaseModel):
    id: str
    startDate: str
    endDate: str
    label: str
    color: str
    confidence: float | str | None = None
    confidenceTier: str | None = None
    explanation: str | None = None
    computedAt: str | None = None
    modelVersion: str | None = None
    signals: str | None = None
    sigLabel: str | None = None
    sigMargin: float | str | None = None
    sourceVersion: str | None = None


class EpisodesLastComputed(BaseModel):
    computedAt: str | None = None
    modelVersion: str | None = None
    episodeCount: int = 0
    wellCount: int = 0
    source: str | None = None
