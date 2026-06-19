import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.graph_export import SCHEMA_VERSION, iter_graph_data_export_csv, iter_manual_graph_data_export_csv


router = APIRouter()
logger = logging.getLogger(__name__)


def _encode_csv_stream(lines):
    first = True
    for line in lines:
        if first:
            yield line.encode("utf-8-sig")
            first = False
        else:
            yield line.encode("utf-8")


def _export_filename(field_code: str | None, well_id: str | None = None) -> str:
    today = date.today().isoformat()
    field_suffix = ""
    well_suffix = ""
    if field_code:
        parts = [part.strip() for part in field_code.split(",") if part.strip()]
        if parts:
            field_suffix = "_" + "_".join(parts)
    if well_id:
        parts = [part.strip() for part in well_id.split(",") if part.strip()]
        if parts:
            well_suffix = "_" + "_".join(parts[:5])
            if len(parts) > 5:
                well_suffix += f"_plus_{len(parts) - 5}"
    return f"well_graph_data{field_suffix}{well_suffix}_{today}.csv"


def _manual_export_filename(field_code: str | None) -> str:
    today = date.today().isoformat()
    field_suffix = ""
    if field_code:
        parts = [part.strip() for part in field_code.split(",") if part.strip()]
        if parts:
            field_suffix = "_" + "_".join(parts)
    return f"well_graph_data_manual{field_suffix}_{today}.csv"


@router.get("/export/graph-data.csv")
def export_graph_data_csv(
    field_code: str | None = Query(default=None),
    well_id: str | None = Query(default=None),
) -> StreamingResponse:
    try:
        csv_lines = iter_graph_data_export_csv(field_code=field_code, well_id=well_id)
    except Exception:
        logger.exception("Failed to build graph data export")
        raise HTTPException(status_code=500, detail="Failed to build graph data export")

    return StreamingResponse(
        _encode_csv_stream(csv_lines),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_export_filename(field_code, well_id)}"',
            "X-Schema-Version": SCHEMA_VERSION,
            "Cache-Control": "no-store",
        },
    )


@router.get("/export/manual-graph-data.csv")
def export_manual_graph_data_csv(field_code: str | None = Query(default=None)) -> StreamingResponse:
    try:
        csv_lines = iter_manual_graph_data_export_csv(field_code=field_code)
    except Exception:
        logger.exception("Failed to build manual graph data export")
        raise HTTPException(status_code=500, detail="Failed to build manual graph data export")

    return StreamingResponse(
        _encode_csv_stream(csv_lines),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_manual_export_filename(field_code)}"',
            "X-Schema-Version": SCHEMA_VERSION,
            "X-Export-Scope": "manual-only",
            "Cache-Control": "no-store",
        },
    )
