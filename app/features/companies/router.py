from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.features.companies import service
from app.features.companies.schemas import CompanyDetailOut, CompanyListItem, CompanyReviewOut, RejectIn
from app.features.users.model import User

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyListItem])
def list_companies(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "director")),
):
    return service.list_companies(db, status, limit, offset)


@router.post("/{company_id}/verify", response_model=CompanyReviewOut)
def verify_company(
    company_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin", "director")),
):
    return service.verify_company(db, company_id, admin)


@router.post("/{company_id}/reject", response_model=CompanyReviewOut)
def reject_company(
    company_id: int,
    body: RejectIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin", "director")),
):
    return service.reject_company(db, company_id, body.reason, admin)


@router.get("/{company_id}", response_model=CompanyDetailOut)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "director")),
):
    return service.get_company_detail(db, company_id)
