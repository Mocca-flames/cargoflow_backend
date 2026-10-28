from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_active_user
from app.core.storage import LocalStorage, get_storage
from app.features.documents import service
from app.features.documents.schemas import DocumentOut
from app.features.users.model import User

router = APIRouter(prefix="/documents", tags=["documents"])


# Plain def (not async): the blocking file save runs in FastAPI's threadpool.
@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    document_type_id: int | None = Form(None),
    custom_label: str | None = Form(None),
    company_id: int | None = Form(None),
    expiry_date: date | None = Form(None),
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
    storage: LocalStorage = Depends(get_storage),
):
    return service.upload_document(
        db, storage, user, file, document_type_id, company_id, expiry_date, custom_label
    )