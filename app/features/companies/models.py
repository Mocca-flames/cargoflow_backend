from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.database import Base

# Plain strings (not Postgres enums) so adding values later needs no painful migration.
COMPANY_STATUSES = ("unverified", "verified", "rejected", "suspended")
COMPANY_ROLES = ("transporter", "broker")  # "client" comes in phase 2


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("country_code", "registration_number", name="uq_company_country_regno"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), index=True)
    trading_name: Mapped[str | None] = mapped_column(String(255))
    registration_number: Mapped[str] = mapped_column(String(50))
    country_code: Mapped[str] = mapped_column(String(2), default="ZA", server_default="ZA", index=True)
    tax_number: Mapped[str | None] = mapped_column(String(50))
    vat_number: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(16))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(20), default="unverified", server_default="unverified", index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_companies_verified_by_users"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list["CompanyRole"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    transporter_profile: Mapped["TransporterProfile | None"] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )
    broker_profile: Mapped["BrokerProfile | None"] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )

    @validates("country_code")
    def _upper_country(self, _: str, value: str) -> str:
        return value.upper().strip()


class CompanyRole(Base):
    """A company can be a transporter, a broker, or both."""
    __tablename__ = "company_roles"
    __table_args__ = (UniqueConstraint("company_id", "role", name="uq_company_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))

    company: Mapped[Company] = relationship(back_populates="roles")


class TransporterProfile(Base):
    __tablename__ = "transporter_profiles"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    operating_countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)), default=list, server_default=text("'{}'")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="transporter_profile")


class BrokerProfile(Base):
    __tablename__ = "broker_profiles"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    corridors: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), default=list, server_default=text("'{}'")
    )  # e.g. "ZA-ZM", "ZA-ZW"
    finds_trucks: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="broker_profile")