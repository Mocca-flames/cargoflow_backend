from datetime import datetime
from typing import Literal
from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


class DocumentOut(BaseModel):
    id: int
    company_id: int
    document_type_id: int | None
    truck_id: int | None
    custom_label: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    expiry_date: datetime | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def note_required_on_reject(self):
        if self.decision == "rejected" and not (self.note or "").strip():
            raise ValueError("A note is required when rejecting")
        return self