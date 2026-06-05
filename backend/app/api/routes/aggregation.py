import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import settings
from app.schemas.aggregation import (
    AggregateRequest,
    AggregationStartResponse,
    AggregationStatusResponse,
    UpdateRequest,
)
from app.services.telemetry_aggregation import get_aggregation_status, run_aggregation, update_wells


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/aggregate", response_model=AggregationStartResponse)
def aggregate_telemetry(
    request: AggregateRequest,
    background_tasks: BackgroundTasks,
) -> AggregationStartResponse:
    try:
        background_tasks.add_task(
            run_aggregation,
            settings.telemetry_data_path,
            request.frequency_threshold,
            request.telemetry_threshold,
        )
    except Exception:
        logger.exception("Failed to start telemetry aggregation")
        raise HTTPException(status_code=500, detail="Failed to start telemetry aggregation")

    return AggregationStartResponse(status="started")


@router.post("/aggregate/update", response_model=AggregationStartResponse)
def update_telemetry_aggregation(
    request: UpdateRequest,
    background_tasks: BackgroundTasks,
) -> AggregationStartResponse:
    source_folder = Path(request.source_folder)
    if not source_folder.exists() or not source_folder.is_dir():
        raise HTTPException(status_code=400, detail="source_folder does not exist or is not a directory")

    try:
        background_tasks.add_task(
            update_wells,
            source_folder,
            settings.telemetry_data_path,
            request.frequency_threshold,
            request.telemetry_threshold,
        )
    except Exception:
        logger.exception("Failed to start telemetry aggregation update")
        raise HTTPException(status_code=500, detail="Failed to start telemetry aggregation update")

    return AggregationStartResponse(status="started")


@router.get("/aggregate/status", response_model=AggregationStatusResponse)
def get_telemetry_aggregation_status() -> AggregationStatusResponse:
    status = get_aggregation_status()
    return AggregationStatusResponse(
        status=status.status,
        wells_done=status.wells_done,
        wells_total=status.wells_total,
        message=status.message,
    )
