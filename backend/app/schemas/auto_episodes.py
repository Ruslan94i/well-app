from pydantic import BaseModel


class AutoEpisodeInterval(BaseModel):
    id: str
    startDate: str
    endDate: str
    label: str
    color: str
    confidence: float | str | None = None
    sourceVersion: str | None = None
