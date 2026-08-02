import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.timeseries import TimeSeriesPoint
from app.services.csv_timeseries import (
    get_available_well_ids,
    get_well_timeseries as get_well_timeseries_from_csv,
)
from app.services.ozna import get_ozna_raw_rows_for_session, get_ozna_sessions_for_well


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/timeseries", response_model=list[TimeSeriesPoint])
def get_well_timeseries(
    well_id: str,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[TimeSeriesPoint]:
    try:
        return get_well_timeseries_from_csv(well_id=well_id, date_from=date_from, date_to=date_to)
    except Exception:
        logger.exception(
            "Failed to load timeseries for well_id=%s date_from=%s date_to=%s",
            well_id,
            date_from,
            date_to,
        )
        raise HTTPException(status_code=500, detail="Failed to load well timeseries data")


@router.get("/wells", response_model=list[str])
def get_wells() -> list[str]:
    try:
        return get_available_well_ids()
    except Exception:
        logger.exception("Failed to load well ids")
        raise HTTPException(status_code=500, detail="Failed to load well list")


@router.get("/wells/{well_id}/ozna-sessions", response_model=list[dict[str, object]])
def get_well_ozna_sessions(well_id: str) -> list[dict[str, object]]:
    try:
        return get_ozna_sessions_for_well(well_id)
    except Exception:
        logger.exception("Failed to load OZNA sessions for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load OZNA sessions")


@router.get("/ozna/sessions/{session_id}/raw", response_model=list[dict[str, object]])
def get_ozna_session_raw(session_id: str) -> list[dict[str, object]]:
    try:
        return get_ozna_raw_rows_for_session(session_id)
    except Exception:
        logger.exception("Failed to load OZNA raw rows for session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="Failed to load OZNA session raw rows")
