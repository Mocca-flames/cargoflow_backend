from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legal_name: str
    trading_name: str | None
    registration_number: str
    country_code: str
    phone: str | None
    status: str
    roles: list[str]
    created_at: datetime


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class CompanyReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    verified_at: datetime | None
    verified_by: int | None
    rejection_reason: str | None
