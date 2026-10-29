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


class CompanyUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str | None


class CompanyDocSummary(BaseModel):
    id: int
    document_type_id: int | None
    type_name: str | None
    custom_label: str | None
    truck_id: int | None
    status: str
    expiry_date: datetime | None
    original_filename: str
    created_at: datetime


class CompanyDetailOut(BaseModel):
    id: int
    legal_name: str
    trading_name: str | None
    registration_number: str
    country_code: str
    tax_number: str | None
    vat_number: str | None
    email: str | None
    phone: str | None
    address: str | None
    city: str | None
    status: str
    verified_at: datetime | None
    verified_by: int | None
    rejection_reason: str | None
    created_at: datetime
    roles: list[str]
    operating_countries: list[str] | None
    corridors: list[str] | None
    finds_trucks: bool | None
    users: list[CompanyUserOut]
    documents: list[CompanyDocSummary]
    missing_documents: list[str]
