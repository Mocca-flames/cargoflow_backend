from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.database import Base

# Plain strings, not PG enums.
TRUCK_TYPES = ("superlink", "flatbed", "tautliner", "tipper", "tanker", "refrigerated", "container", "side_tipper", "other")


class Truck(Base):
    __tablename__ = "trucks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    registration_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    truck_type: Mapped[str] = mapped_column(String(30), index=True)
    capacity_tons: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @validates("registration_number")
    def _norm_reg(self, _: str, value: str) -> str:
        return "".join(value.split()).upper()
