import logging

from fastapi import APIRouter, HTTPException

from app.schemas.auto_episodes import AutoEpisodeInterval
from app.services.auto_episodes import get_well_auto_episode_intervals


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/auto-episodes", response_model=list[AutoEpisodeInterval])
def get_well_auto_episodes(well_id: str) -> list[AutoEpisodeInterval]:
    try:
        return get_well_auto_episode_intervals(well_id)
    except Exception:
        logger.exception("Failed to load auto episode intervals for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load auto episode intervals")
