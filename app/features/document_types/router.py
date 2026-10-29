from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_active_user, require_role
from app.features.document_types import service
from app.features.document_types.schemas import DocumentTypeCreate, DocumentTypeOut, DocumentTypeUpdate, SuggestedTypeOut
from app.features.users.model import User

router = APIRouter(prefix="/document-types", tags=["document-types"])


@router.get("", response_model=list[DocumentTypeOut])
def list_types(
    applies_to: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_active_user),
):
    return service.list_types(db, applies_to, active)


@router.post("", response_model=DocumentTypeOut, status_code=201)
def create_type(
    body: DocumentTypeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin", "director")),
):
    return service.create_type(db, body, admin)


@router.patch("/{type_id}", response_model=DocumentTypeOut)
def update_type(
    type_id: int,
    body: DocumentTypeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "director")),
):
    return service.update_type(db, type_id, body)


@router.get("/suggestions", response_model=list[SuggestedTypeOut])
def suggested_types(
    min_companies: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "director")),
):
    return service.suggested_types(db, min_companies, limit)
