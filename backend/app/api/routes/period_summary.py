from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas.period_summary import PeriodSummaryResponse
from app.services.period_summary import build_period_summary


router = APIRouter()


@router.get("/period-summary", response_model=PeriodSummaryResponse)
def get_period_summary(
    period: Literal["week", "month", "year", "custom"] = Query("week"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    field_code: str | None = Query(None),
    well_id: str | None = Query(None),
) -> PeriodSummaryResponse:
    try:
        return build_period_summary(period, date_from, date_to, field_code, well_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to build period summary") from exc
