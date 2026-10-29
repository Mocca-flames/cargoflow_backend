from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.features.companies.models import Company
from app.features.documents.models import CompanyDocument, DocumentType
from app.features.users.model import User
from app.features.companies.schemas import CompanyListItem


def list_companies(db: Session, status: str | None, limit: int, offset: int) -> list[CompanyListItem]:
    q = select(Company).options(selectinload(Company.roles)).order_by(Company.created_at.desc())
    if status:
        q = q.where(Company.status == status)
    rows = db.scalars(q.limit(limit).offset(offset)).all()
    return [
        CompanyListItem(
            id=c.id,
            legal_name=c.legal_name,
            trading_name=c.trading_name,
            registration_number=c.registration_number,
            country_code=c.country_code,
            phone=c.phone,
            status=c.status,
            roles=[r.role for r in c.roles],
            created_at=c.created_at,
        )
        for c in rows
    ]


def _get_company(db: Session, company_id: int) -> Company:
    company = db.scalar(
        select(Company).options(selectinload(Company.roles)).where(Company.id == company_id)
    )
    if not company:
        raise HTTPException(404, "Company not found.")
    return company


def _missing_documents(db: Session, company: Company) -> list[str]:
    roles = [r.role for r in company.roles]
    types = db.scalars(
        select(DocumentType).where(
            DocumentType.is_active.is_(True),
            DocumentType.is_required.is_(True),
            DocumentType.applies_to.in_(roles),
            (DocumentType.country_code == company.country_code) | (DocumentType.country_code.is_(None)),
        )
    ).all()
    approved_ids = set(db.scalars(
        select(CompanyDocument.document_type_id).where(
            CompanyDocument.company_id == company.id,
            CompanyDocument.status == "approved",
            CompanyDocument.truck_id.is_(None),
        )
    ).all())
    return sorted({f"{t.name} ({t.applies_to})" for t in types if t.id not in approved_ids})


def verify_company(db: Session, company_id: int, admin: User) -> Company:
    company = _get_company(db, company_id)
    if company.status not in ("unverified", "rejected"):
        raise HTTPException(409, f"Cannot verify a company that is {company.status}.")
    missing = _missing_documents(db, company)
    if missing:
        raise HTTPException(409, "Missing approved documents: " + ", ".join(missing))
    company.status = "verified"
    company.verified_at = datetime.now(timezone.utc)
    company.verified_by = admin.id
    company.rejection_reason = None
    db.commit()
    db.refresh(company)
    return company


def reject_company(db: Session, company_id: int, reason: str, admin: User) -> Company:
    company = _get_company(db, company_id)
    if company.status not in ("unverified", "verified"):
        raise HTTPException(409, f"Cannot reject a company that is {company.status}.")
    company.status = "rejected"
    company.rejection_reason = reason.strip()
    company.verified_at = None
    company.verified_by = None
    db.commit()
    db.refresh(company)
    return company
