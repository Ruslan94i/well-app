import logging

from fastapi import APIRouter, HTTPException

from app.schemas.context import WellContext
from app.services.xlsx_reference import get_well_context as get_well_context_from_reference


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/context", response_model=WellContext)
def get_well_context(well_id: str) -> WellContext:
    try:
        return get_well_context_from_reference(well_id)
    except Exception:
        logger.exception("Failed to load well context for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load well context")
