import logging

from fastapi import APIRouter, HTTPException

from app.schemas.model_params import ModelParamOverrides, ModelParamsState, ModelParamValue
from app.services.model_params import (
    PARAMS,
    get_params,
    load_overrides,
    replace_target_overrides,
    reset_well_params,
    set_param_override,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/model-params", response_model=ModelParamsState)
def get_model_params_state() -> ModelParamsState:
    return ModelParamsState(globalParams=PARAMS.copy(), overrides=load_overrides())


@router.get("/wells/{well_id}/model-params", response_model=dict[str, float])
def get_well_model_params(well_id: str) -> dict[str, float]:
    return get_params(well_id)


@router.put("/model-params/{target_id}", response_model=ModelParamsState)
def put_target_model_params(target_id: str, payload: ModelParamOverrides) -> ModelParamsState:
    try:
        overrides = replace_target_overrides(target_id, payload.params)
    except Exception:
        logger.exception("Failed to save model parameter overrides for target_id=%s", target_id)
        raise HTTPException(status_code=500, detail="Failed to save model parameter overrides")

    return ModelParamsState(globalParams=PARAMS.copy(), overrides=overrides)


@router.put("/model-params/{target_id}/{param_key}", response_model=ModelParamsState)
def put_model_param_override(target_id: str, param_key: str, payload: ModelParamValue) -> ModelParamsState:
    try:
        overrides = set_param_override(target_id, param_key, payload.value)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown model parameter: {param_key}")
    except Exception:
        logger.exception(
            "Failed to save model parameter override target_id=%s param_key=%s",
            target_id,
            param_key,
        )
        raise HTTPException(status_code=500, detail="Failed to save model parameter override")

    return ModelParamsState(globalParams=PARAMS.copy(), overrides=overrides)


@router.delete("/model-params/{target_id}", response_model=ModelParamsState)
def delete_target_model_params(target_id: str) -> ModelParamsState:
    try:
        overrides = reset_well_params(target_id)
    except Exception:
        logger.exception("Failed to reset model parameter overrides for target_id=%s", target_id)
        raise HTTPException(status_code=500, detail="Failed to reset model parameter overrides")

    return ModelParamsState(globalParams=PARAMS.copy(), overrides=overrides)
