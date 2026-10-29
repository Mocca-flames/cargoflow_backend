from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.availability.models import AVAILABILITY_STATUSES


class AvailabilityCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    truck_id: int
    status: str
    location: str = Field(min_length=2, max_length=100)
    destination: str | None = Field(default=None, max_length=100)
    available_from: date | None = None  # defaults to today
    days_valid: int = Field(default=3, ge=1, le=14)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in AVAILABILITY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(AVAILABILITY_STATUSES)}")
        return v

    @field_validator("destination")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() or None if v else v


class AvailabilityOut(BaseModel):
    id: int
    truck_id: int
    company_id: int
    registration_number: str
    truck_type: str
    capacity_tons: Decimal | None
    status: str
    location: str
    destination: str | None
    available_from: date
    expires_at: datetime
    note: str | None
    created_at: datetime
