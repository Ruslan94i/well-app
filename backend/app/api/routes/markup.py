import logging

from fastapi import APIRouter, HTTPException

from app.schemas.markup import MarkupState
from app.services.json_markup import load_markup_state, save_markup_state


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/markup", response_model=MarkupState)
def get_markup() -> MarkupState:
    try:
        return load_markup_state()
    except Exception:
        logger.exception("Failed to load markup")
        raise HTTPException(status_code=500, detail="Failed to load markup")


@router.put("/markup", response_model=MarkupState)
def put_markup(markup: MarkupState) -> MarkupState:
    try:
        return save_markup_state(markup)
    except Exception:
        logger.exception("Failed to save markup")
        raise HTTPException(status_code=500, detail="Failed to save markup")
