from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.database import Base
from app.core.normalize_phone import normalize_phone


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL", use_alter=True, name="fk_users_company_id_companies"),index=True,)
    staff_role: Mapped[str] = mapped_column(String(50), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[int | None] = mapped_column(Integer)

    @validates("email")
    def _lowercase_email(self, _: str, value: str | None) -> str | None:
        return value.lower().strip() if value else value

    @validates("phone")
    def _validate_phone(self, _: str, value: str | None) -> str | None:
        return normalize_phone(value) if value else None
