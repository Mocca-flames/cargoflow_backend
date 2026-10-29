from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Plain strings, not PG enums.
AVAILABILITY_STATUSES = ("available", "needs_backload")


class TruckAvailability(Base):
    __tablename__ = "truck_availability"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    truck_id: Mapped[int] = mapped_column(ForeignKey("trucks.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    location: Mapped[str] = mapped_column(String(100))
    destination: Mapped[str | None] = mapped_column(String(100))
    available_from: Mapped[date] = mapped_column(Date)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
