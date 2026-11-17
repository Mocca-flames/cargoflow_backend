from datetime import date, datetime

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: date
    new_interests: int
    onboarded_companies: int


class Overview(BaseModel):
    open_loads: int
    unverified_companies: int
    new_interests: int
    onboarded_companies_7d: int  # verified in last 7 days
    converted_leads_7d: int  # interests turned into companies (onboarded) in last 7 days
    trend: list[TrendPoint]  # 14 days, zero-filled
    generated_at: datetime
