from fastapi import APIRouter

from app.api.routes.artificial_lift import router as artificial_lift_router
from app.api.routes.context import router as context_router
from app.api.routes.export import router as export_router
from app.api.routes.health import router as health_router
from app.api.routes.markup import router as markup_router
from app.api.routes.timeseries import router as timeseries_router
from app.api.routes.tr_monitoring import router as tr_monitoring_router
from app.api.routes.vsp import router as vsp_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(export_router, tags=["export"])
api_router.include_router(timeseries_router, tags=["timeseries"])
api_router.include_router(artificial_lift_router, tags=["artificial-lift"])
api_router.include_router(tr_monitoring_router, tags=["tr-monitoring"])
api_router.include_router(context_router, tags=["context"])
api_router.include_router(vsp_router, tags=["vsp"])
api_router.include_router(markup_router, tags=["markup"])
