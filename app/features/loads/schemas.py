from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.features.loads.models import CURRENCIES, LOAD_STATUSES, PAYMENT_TERMS
from app.features.trucks.models import TRUCK_TYPES

Money = Decimal


def _one_of(value: str | None, allowed: tuple[str, ...], name: str, upper: bool = False) -> str | None:
    if value is None:
        return value
    value = value.upper() if upper else value.lower()
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return value


def _free_text(value: str | None, name: str, max_len: int = 100) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > max_len:
        raise ValueError(f"{name} must be at most {max_len} characters")
    return value


class LoadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    origin: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    commodity: str = Field(min_length=2, max_length=150)
    truck_type: str | None = None
    trucks_needed: int = Field(default=1, ge=1, le=200)
    rate: Money = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = "USD"
    payment_terms: str | None = None
    pickup_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)
    company_id: int | None = None  # staff only; broker users post for their own company

    # Optional backload, same currency as the load.
    backload_origin: str | None = Field(default=None, min_length=2, max_length=100)
    backload_destination: str | None = Field(default=None, min_length=2, max_length=100)
    backload_commodity: str | None = Field(default=None, max_length=150)
    backload_rate: Money | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)

    @field_validator("truck_type")
    @classmethod
    def _truck_type(cls, v):
        return _one_of(v, TRUCK_TYPES, "truck_type")

    @field_validator("currency")
    @classmethod
    def _currency(cls, v):
        return _one_of(v, CURRENCIES, "currency", upper=True)

    @field_validator("payment_terms")
    @classmethod
    def _terms(cls, v):
        return _free_text(v, "payment_terms")

    @field_validator("pickup_date")
    @classmethod
    def _not_past(cls, v):
        if v is not None and v < datetime.now(timezone.utc).date():
            raise ValueError("pickup_date is in the past")
        return v

    @model_validator(mode="after")
    def _backload_complete(self):
        parts = (self.backload_origin, self.backload_destination, self.backload_commodity, self.backload_rate)
        if any(p is not None for p in parts) and not (self.backload_origin and self.backload_destination):
            raise ValueError("A backload needs backload_origin and backload_destination")
        return self


class LoadUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str | None = None
    trucks_needed: int | None = Field(default=None, ge=1, le=200)
    rate: Money | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    payment_terms: str | None = None
    pickup_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        return _one_of(v, LOAD_STATUSES, "status")

    @field_validator("payment_terms")
    @classmethod
    def _terms(cls, v):
        return _free_text(v, "payment_terms")


class LoadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    commodity: str
    truck_type: str | None
    trucks_needed: int
    rate: Money
    currency: str
    payment_terms: str | None
    pickup_date: date | None
    status: str
    note: str | None
    backload_origin: str | None
    backload_destination: str | None
    backload_commodity: str | None
    backload_rate: Money | None
    company_id: int | None
    created_at: datetime

    @computed_field
    @property
    def has_backload(self) -> bool:
        return self.backload_origin is not None


class PublicLoadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    commodity: str
    truck_type: str | None
    trucks_needed: int
    rate: Money
    currency: str
    payment_terms: str | None
    pickup_date: date | None
    backload_origin: str | None
    backload_destination: str | None
    backload_commodity: str | None
    backload_rate: Money | None
    created_at: datetime

    @computed_field
    @property
    def has_backload(self) -> bool:
        return self.backload_origin is not None
