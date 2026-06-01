import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.graph_export import build_graph_data_export_csv


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/export/graph-data.csv")
def export_graph_data_csv() -> Response:
    try:
        csv_content = build_graph_data_export_csv()
    except Exception:
        logger.exception("Failed to build graph data export")
        raise HTTPException(status_code=500, detail="Failed to build graph data export")

    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="well_graph_data.csv"'},
    )
