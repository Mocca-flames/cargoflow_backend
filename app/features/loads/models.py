from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Plain strings, not PG enums.
LOAD_STATUSES = ("open", "assigned", "closed")
CURRENCIES = ("USD", "ZAR")
PAYMENT_TERMS = ("on_delivery", "7_days", "14_days", "30_days", "50_advance")


class Load(Base):
    __tablename__ = "loads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    origin: Mapped[str] = mapped_column(String(100), index=True)
    destination: Mapped[str] = mapped_column(String(100), index=True)
    commodity: Mapped[str] = mapped_column(String(150))
    truck_type: Mapped[str | None] = mapped_column(String(30), index=True)
    trucks_needed: Mapped[int] = mapped_column(Integer)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # per truck
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    pickup_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open", index=True)
    note: Mapped[str | None] = mapped_column(Text)

    # Optional backload (same currency as the load). Set backload_origin to turn it on.
    backload_origin: Mapped[str | None] = mapped_column(String(100))
    backload_destination: Mapped[str | None] = mapped_column(String(100))
    backload_commodity: Mapped[str | None] = mapped_column(String(150))
    backload_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
