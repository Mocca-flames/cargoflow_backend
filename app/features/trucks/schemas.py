from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.trucks.models import TRUCK_TYPES


def _check_type(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().lower()
    if v not in TRUCK_TYPES:
        raise ValueError(f"truck_type must be one of: {', '.join(TRUCK_TYPES)}")
    return v


class TruckCreate(BaseModel):
    company_id: int | None = None  # admins must set it; transporters use their own company
    registration_number: str = Field(min_length=3, max_length=20)
    truck_type: str
    capacity_tons: Decimal | None = Field(default=None, gt=0, le=200, max_digits=6, decimal_places=2)

    _v_type = field_validator("truck_type")(_check_type)


class TruckUpdate(BaseModel):
    truck_type: str | None = None
    capacity_tons: Decimal | None = Field(default=None, gt=0, le=200, max_digits=6, decimal_places=2)
    is_active: bool | None = None
    registration_number: str | None = Field(default=None, min_length=3, max_length=20)

    _v_type = field_validator("truck_type")(_check_type)


class TruckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    registration_number: str
    truck_type: str
    capacity_tons: Decimal | None
    is_active: bool
    created_at: datetime


class TruckDetail(TruckOut):
    docs_complete: bool
    missing: list[str]
