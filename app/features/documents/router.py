from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile, Query
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_active_user, require_role
from app.core.storage import LocalStorage, get_storage
from app.features.documents import service
from app.features.documents.schemas import DocumentOut
from app.features.users.model import User
from app.features.documents.schemas import ReviewIn

router = APIRouter(prefix="/documents", tags=["documents"])
inline: bool = Query(False)


# Plain def (not async): the blocking file save runs in FastAPI's threadpool.
@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    document_type_id: int | None = Form(None),
    custom_label: str | None = Form(None),
    company_id: int | None = Form(None),
    expiry_date: date | None = Form(None),
    truck_id: int | None = Form(None),
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
    storage: LocalStorage = Depends(get_storage),
):
    return service.upload_document(
        db, storage, user, file, document_type_id, company_id, expiry_date, custom_label, truck_id
    )

@router.get("", response_model=list[DocumentOut])
def list_documents(
    company_id: int | None = Query(None),
    status: str | None = Query(None, pattern="^(pending|approved|rejected|superseded)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
):
    return service.list_documents(db, user, company_id, status, limit, offset)

@router.get("/{doc_id}/download")
def download_document(
    doc_id: int,
    inline: bool = Query(False),
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
    storage: LocalStorage = Depends(get_storage),
):
    doc, path = service.get_document_for_download(db, storage, user, doc_id)
    return FileResponse(
        path,
        media_type=doc.content_type,
        filename=doc.original_filename,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/{doc_id}/review", response_model=DocumentOut)
def review_document(
    doc_id: int,
    body: ReviewIn,
    user: User = Depends(require_role("admin", "director")),
    db: Session = Depends(get_db),
):
    return service.review_document(db, user, doc_id, body.decision, body.note, body.expiry_date)