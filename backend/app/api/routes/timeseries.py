from datetime import date

from fastapi import APIRouter, Query

from app.schemas.timeseries import TimeSeriesPoint
from app.services.mock_timeseries import generate_well_timeseries


router = APIRouter()


@router.get("/wells/{well_id}/timeseries", response_model=list[TimeSeriesPoint])
def get_well_timeseries(
    well_id: str,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[TimeSeriesPoint]:
    return generate_well_timeseries(well_id=well_id, date_from=date_from, date_to=date_to)

