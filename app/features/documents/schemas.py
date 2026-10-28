from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    id: int
    company_id: int
    document_type_id: int | None
    custom_label: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    expiry_date: datetime | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)