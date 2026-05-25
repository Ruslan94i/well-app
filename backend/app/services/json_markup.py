from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.markup import MarkupState


logger = logging.getLogger(__name__)
MARKUP_FILE_PATH = settings.markup_data_path


def load_markup_state() -> MarkupState:
    if not MARKUP_FILE_PATH.exists():
        return MarkupState()

    try:
        raw_state = json.loads(MARKUP_FILE_PATH.read_text(encoding="utf-8"))
        return MarkupState.model_validate(raw_state)
    except (OSError, json.JSONDecodeError, ValidationError):
        logger.exception("Failed to load markup from %s", MARKUP_FILE_PATH)
        raise


def save_markup_state(markup: MarkupState) -> MarkupState:
    MARKUP_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MARKUP_FILE_PATH.with_suffix(f"{MARKUP_FILE_PATH.suffix}.tmp")
    payload = json.dumps(markup.model_dump(mode="json"), ensure_ascii=False, indent=2)

    try:
        tmp_path.write_text(f"{payload}\n", encoding="utf-8")
        tmp_path.replace(MARKUP_FILE_PATH)
    except PermissionError:
        logger.warning(
            "Atomic markup save is not allowed for %s; falling back to direct write",
            MARKUP_FILE_PATH,
        )
        MARKUP_FILE_PATH.write_text(f"{payload}\n", encoding="utf-8")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Failed to remove temporary markup file %s", tmp_path, exc_info=True)
    except OSError:
        logger.exception("Failed to save markup to %s", MARKUP_FILE_PATH)
        raise

    return markup
