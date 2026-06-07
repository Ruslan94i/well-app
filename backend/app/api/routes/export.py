import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.graph_export import SCHEMA_VERSION, build_graph_data_export_csv


router = APIRouter()
logger = logging.getLogger(__name__)


def _export_filename(field_code: str | None) -> str:
    today = date.today().isoformat()
    field_suffix = ""
    if field_code:
        parts = [part.strip() for part in field_code.split(",") if part.strip()]
        if parts:
            field_suffix = "_" + "_".join(parts)
    return f"well_graph_data{field_suffix}_{today}.csv"


@router.get("/export/graph-data.csv")
def export_graph_data_csv(field_code: str | None = Query(default=None)) -> Response:
    try:
        csv_content = build_graph_data_export_csv(field_code=field_code)
    except Exception:
        logger.exception("Failed to build graph data export")
        raise HTTPException(status_code=500, detail="Failed to build graph data export")

    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_export_filename(field_code)}"',
            "X-Schema-Version": SCHEMA_VERSION,
        },
    )
