from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.normalize_phone import normalize_phone

STAFF_ROLES = {'director', 'admin', 'manager', 'technician'}


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    phone: str | None = None
    staff_role: str = 'user'      # 'user' = client, broker or transporter
    company_id: int | None = None

    @field_validator('phone')
    @classmethod
    def clean_phone(cls, v):
        return normalize_phone(v) if v else None


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    staff_role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)