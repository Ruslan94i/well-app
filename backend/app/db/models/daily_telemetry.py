from datetime import date

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyTelemetry(Base):
    __tablename__ = "daily_telemetry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    well_id: Mapped[str] = mapped_column(String(64), index=True)
    telemetry_date: Mapped[date] = mapped_column(Date, index=True)
    qliq: Mapped[float] = mapped_column(Float)
    qoil: Mapped[float] = mapped_column(Float)
    qliq_vfm: Mapped[float] = mapped_column(Float)
    water_cut: Mapped[float] = mapped_column(Float)
    intake_pressure: Mapped[float] = mapped_column(Float)
    esp_frequency: Mapped[float] = mapped_column(Float)
    load: Mapped[float] = mapped_column(Float)

