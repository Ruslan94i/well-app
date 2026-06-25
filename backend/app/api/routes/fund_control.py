from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas.fund_control import FundControlResponse
from app.services.fund_control import build_fund_control


router = APIRouter()


@router.get("/fund-control", response_model=FundControlResponse)
def get_fund_control(
    period: Literal["week", "month", "quarter", "year", "custom"] = Query("month"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    field_code: str | None = Query(None),
    well_id: str | None = Query(None),
) -> FundControlResponse:
    try:
        return build_fund_control(period, date_from, date_to, field_code, well_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to build fund control attribution") from exc
