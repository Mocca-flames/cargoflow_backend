from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func, text, BigInteger, Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Plain strings, not PG enums, so adding values later needs no painful migration.
APPLIES_TO = ("transporter", "broker", "truck")
DOC_STATUSES = ("pending", "approved", "rejected", "superseded")


class DocumentType(Base):
    __tablename__ = "document_types"
    __table_args__ = (
        UniqueConstraint("code", "country_code", "applies_to", name="uq_document_type_code_country_applies_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)  # e.g. "cipc_registration"
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(50), index=True)  # e.g. "company_registration"
    applies_to: Mapped[str] = mapped_column(String(20), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)  # null = every country
    issuing_authority: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    requires_expiry: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_document_types_created_by_users"),)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CompanyDocument(Base):
    __tablename__ = "company_documents"
    __table_args__ = (
        Index("ix_company_documents_company_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    document_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_types.id", ondelete="RESTRICT"), index=True
    )  # null = "Other"
    custom_label: Mapped[str | None] = mapped_column(String(150))  # used when document_type_id is null
    custom_label_norm: Mapped[str | None] = mapped_column(String(150), index=True)  # lowercased, for the suggestions list
    truck_id: Mapped[int | None] = mapped_column(Integer, index=True)  # FK added in Step 6, when trucks exists
    file_path: Mapped[str] = mapped_column(String(500))  # random name on disk
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
