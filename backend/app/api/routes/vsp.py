import logging

from fastapi import APIRouter, HTTPException

from app.schemas.vsp import VspPeriod
from app.services.vsp import get_well_vsp_periods


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/vsp-periods", response_model=list[VspPeriod])
def get_well_vsp(well_id: str) -> list[VspPeriod]:
    try:
        return get_well_vsp_periods(well_id)
    except Exception:
        logger.exception("Failed to load VSP periods for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load VSP data")
