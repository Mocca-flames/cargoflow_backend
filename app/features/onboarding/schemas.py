from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.normalize_phone import normalize_phone


class OwnerIn(BaseModel):
    full_name: str
    email: EmailStr
    phone: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()

    @field_validator("phone")
    @classmethod
    def normalize_owner_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name is required")
        return v


class CompanyIn(BaseModel):
    legal_name: str = Field(max_length=255)
    trading_name: str | None = Field(default=None, max_length=255)
    registration_number: str = Field(min_length=1, max_length=50)
    country_code: str = Field(min_length=2, max_length=2)
    phone: str | None = None

    @field_validator("legal_name")
    @classmethod
    def validate_legal_name(cls, v: str) -> str:
        v = str(v).strip()
        if v == "":
            raise ValueError("legal_name is required")
        return v

    @field_validator("trading_name")
    @classmethod
    def validate_trading_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = str(v).strip()
        return v if v != "" else None

    @field_validator("country_code")
    @classmethod
    def upper_country(cls, v: str) -> str:
        cu = str(v).strip().upper()
        if len(cu) != 2 or not cu.isalpha():
            raise ValueError("country_code must be exactly 2 letters")
        return cu

    @field_validator("registration_number")
    @classmethod
    def strip_regno(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("registration_number is required")
        return v

    @field_validator("phone")
    @classmethod
    def normalize_company_phone(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return normalize_phone(v)


class TransporterIn(BaseModel):
    operating_countries: list[str] = Field(min_length=1)

    @field_validator("operating_countries")
    @classmethod
    def validate_operating_countries(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least 1 operating country required")
        seen = set()
        out = []
        for c in v:
            cu = str(c).strip().upper()
            if len(cu) != 2 or not cu.isalpha():
                raise ValueError("operating_countries must be exactly 2 letters")
            if cu in seen:
                raise ValueError("operating_countries must be unique")
            seen.add(cu)
            out.append(cu)
        return out


class BrokerIn(BaseModel):
    corridors: list[str]
    finds_trucks: bool


class OnboardingStartIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class CompanyOnboardingBase(BaseModel):
    company: CompanyIn
    roles: list[Literal["transporter", "broker"]]
    transporter: TransporterIn | None = None
    broker: BrokerIn | None = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[Literal["transporter", "broker"]]) -> list[Literal["transporter", "broker"]]:
        if len(v) < 1 or len(v) > 2:
            raise ValueError("roles must have 1 to 2 items")
        if len(set(v)) != len(v):
            raise ValueError("roles must be unique")
        return v

    @model_validator(mode="after")
    def validate_role_profiles(self):
        roles_set = set(self.roles)
        if "transporter" in roles_set and self.transporter is None:
            raise ValueError("transporter profile required for transporter role")
        if "broker" in roles_set and self.broker is None:
            raise ValueError("broker profile required for broker role")
        if "transporter" not in roles_set and self.transporter is not None:
            raise ValueError("transporter profile not allowed for unselected role")
        if "broker" not in roles_set and self.broker is not None:
            raise ValueError("broker profile not allowed for unselected role")
        return self


class OnboardingSubmitIn(CompanyOnboardingBase):
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8)
    owner: OwnerIn


class StaffOnboardingIn(CompanyOnboardingBase):
    owner: OwnerIn | None = None
    create_owner: bool = False

    @model_validator(mode="after")
    def validate_create_owner(self):
        if self.create_owner and self.owner is None:
            raise ValueError("owner required when create_owner is True")
        return self


class OnboardingOut(BaseModel):
    company_id: int
    status: str
    roles: list[str]
    owner_user_id: int | None = None
    message: str
