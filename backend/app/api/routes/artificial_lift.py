import logging

from fastapi import APIRouter, HTTPException

from app.schemas.artificial_lift import ArtificialLiftPeriod
from app.services.artificial_lift import get_well_artificial_lift_periods


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/artificial-lift", response_model=list[ArtificialLiftPeriod])
def get_well_artificial_lift(well_id: str) -> list[ArtificialLiftPeriod]:
    try:
        return get_well_artificial_lift_periods(well_id)
    except Exception:
        logger.exception("Failed to load artificial lift periods for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load artificial lift data")
