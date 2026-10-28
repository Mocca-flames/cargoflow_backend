from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MessageOut(BaseModel):
    message: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    device_token: str | None = None


class LoginOut(BaseModel):
    otp_required: bool
    message: str | None = None
    tokens: TokenOut | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class VerifyOtpIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    remember_device: bool = False


class MeOut(BaseModel):
    id: int
    email: str
    full_name: str
    staff_role: str
    company_id: int | None
    must_change_password: bool
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    device_token: str | None = None

class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=10, max_length=128)