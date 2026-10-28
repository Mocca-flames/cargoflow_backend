from pydantic import BaseModel


class OtpIssueRequest(BaseModel):
    email: str
    purpose: str


class OtpVerifyRequest(BaseModel):
    email: str
    purpose: str
    code: str
