import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.tr_monitoring import TrMonitoringPoint
from app.services.tr_monitoring import get_well_tr_monitoring as get_well_tr_monitoring_from_csv


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/tr-monitoring", response_model=list[TrMonitoringPoint])
def get_well_tr_monitoring(
    well_id: str,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[TrMonitoringPoint]:
    try:
        return get_well_tr_monitoring_from_csv(well_id=well_id, date_from=date_from, date_to=date_to)
    except Exception:
        logger.exception(
            "Failed to load TR monitoring for well_id=%s date_from=%s date_to=%s",
            well_id,
            date_from,
            date_to,
        )
        raise HTTPException(status_code=500, detail="Failed to load TR monitoring data")
