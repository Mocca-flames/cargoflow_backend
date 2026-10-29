from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.normalize_phone import normalize_phone
from app.features.onboarding.schemas import CompanyOnboardingBase
from app.features.load_interests.models import INTEREST_STATUSES
from app.features.trucks.models import TRUCK_TYPES


class InterestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=7, max_length=20)
    truck_type: str | None = None
    consent: bool
    website: str | None = Field(default=None, max_length=200)  # honeypot, must stay empty

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("truck_type")
    @classmethod
    def _truck_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if v not in TRUCK_TYPES:
            raise ValueError(f"truck_type must be one of: {', '.join(TRUCK_TYPES)}")
        return v

    @field_validator("consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent to be called is required")
        return v


class InterestReceived(BaseModel):
    message: str


class InterestUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if v not in INTEREST_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(INTEREST_STATUSES)}")
        return v


class InterestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    load_id: int
    load_origin: str
    load_destination: str
    full_name: str
    phone: str
    truck_type: str | None
    status: str
    company_id: int | None
    note: str | None
    created_at: datetime
    handled_at: datetime | None


class ConvertLeadIn(CompanyOnboardingBase):
    create_owner: bool = False
    owner_email: EmailStr | None = None

    @field_validator("owner_email")
    @classmethod
    def _lower_owner_email(cls, v: EmailStr | None) -> str | None:
        return None if v is None else str(v).strip().lower()

    @model_validator(mode="after")
    def _owner_email_required(self):
        if self.create_owner and not self.owner_email:
            raise ValueError("owner_email required when create_owner is True")
        return self
