import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.auto_episodes import AutoEpisodeInterval, EpisodesLastComputed
from app.services.auto_episodes import (
    get_episodes_last_computed,
    get_well_auto_episode_intervals,
    get_well_candidate_auto_episode_intervals,
    get_well_episode_intervals,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/wells/{well_id}/auto-episodes", response_model=list[AutoEpisodeInterval])
def get_well_auto_episodes(well_id: str) -> list[AutoEpisodeInterval]:
    try:
        return get_well_auto_episode_intervals(well_id)
    except Exception:
        logger.exception("Failed to load auto episode intervals for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load auto episode intervals")


@router.get("/wells/{well_id}/candidate-auto-episodes", response_model=list[AutoEpisodeInterval])
def get_well_candidate_auto_episodes(well_id: str) -> list[AutoEpisodeInterval]:
    try:
        return get_well_candidate_auto_episode_intervals(well_id)
    except Exception:
        logger.exception("Failed to load candidate auto episode intervals for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load candidate auto episode intervals")


@router.get("/wells/{well_id}/episodes", response_model=list[AutoEpisodeInterval])
def get_well_episodes(
    well_id: str,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    label: str | None = Query(default=None),
    tier: str | None = Query(default=None),
) -> list[AutoEpisodeInterval]:
    try:
        return get_well_episode_intervals(well_id, date_from=date_from, date_to=date_to, label=label, tier=tier)
    except Exception:
        logger.exception("Failed to load ready episode intervals for well_id=%s", well_id)
        raise HTTPException(status_code=500, detail="Failed to load ready episode intervals")


@router.get("/episodes/last-computed", response_model=EpisodesLastComputed)
@router.get("/episodes/last_computed", response_model=EpisodesLastComputed)
def get_last_computed() -> EpisodesLastComputed:
    try:
        return get_episodes_last_computed()
    except Exception:
        logger.exception("Failed to load last computed episode metadata")
        raise HTTPException(status_code=500, detail="Failed to load last computed episode metadata")
