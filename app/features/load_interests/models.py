from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Plain strings, not PG enums.
INTEREST_STATUSES = ("new", "contacted", "onboarded", "dismissed")


class LoadInterest(Base):
    __tablename__ = "load_interests"
    __table_args__ = (
        UniqueConstraint("load_id", "phone", name="uq_load_interest_load_phone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    load_id: Mapped[int] = mapped_column(ForeignKey("loads.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(16), index=True)
    truck_type: Mapped[str | None] = mapped_column(String(30))
    consent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
