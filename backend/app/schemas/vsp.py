from pydantic import BaseModel


class VspPeriod(BaseModel):
    id: str
    wellId: str
    startDate: str
    endDate: str
    status: str
    wellState: str
    wellStateCode: str
