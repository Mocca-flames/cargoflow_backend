from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AppliesTo = Literal["transporter", "broker", "truck"]


class DocumentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: str
    applies_to: str
    country_code: str | None
    issuing_authority: str | None
    description: str | None
    is_required: bool
    requires_expiry: bool
    is_active: bool
    sort_order: int


class DocumentTypeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=50)
    applies_to: AppliesTo
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    issuing_authority: str | None = Field(default=None, max_length=150)
    description: str | None = None
    is_required: bool = True
    requires_expiry: bool = False
    sort_order: int = 0

    @field_validator("country_code")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else v


class DocumentTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    category: str | None = Field(default=None, min_length=2, max_length=50)
    issuing_authority: str | None = Field(default=None, max_length=150)
    description: str | None = None
    is_required: bool | None = None
    requires_expiry: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
