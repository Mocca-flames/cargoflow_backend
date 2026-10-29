from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.document_types.schemas import DocumentTypeCreate, DocumentTypeUpdate
from app.features.documents.models import CompanyDocument, DocumentType
from app.features.users.model import User


def list_types(db: Session, applies_to: str | None, active: bool | None) -> list[DocumentType]:
    q = select(DocumentType).order_by(DocumentType.sort_order, DocumentType.id)
    if applies_to:
        q = q.where(DocumentType.applies_to == applies_to)
    if active is not None:
        q = q.where(DocumentType.is_active.is_(active))
    return list(db.scalars(q).all())


def create_type(db: Session, body: DocumentTypeCreate, admin: User) -> DocumentType:
    exists = db.scalar(select(DocumentType.id).where(
        DocumentType.code == body.code,
        DocumentType.applies_to == body.applies_to,
        DocumentType.country_code.is_(None) if body.country_code is None
        else DocumentType.country_code == body.country_code,
    ))
    if exists:
        raise HTTPException(409, "A document type with this code already exists for that role and country.")
    dt = DocumentType(**body.model_dump(), created_by=admin.id)
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt


def update_type(db: Session, type_id: int, body: DocumentTypeUpdate) -> DocumentType:
    dt = db.get(DocumentType, type_id)
    if not dt:
        raise HTTPException(404, "Document type not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(dt, field, value)
    db.commit()
    db.refresh(dt)
    return dt


def suggested_types(db: Session, min_companies: int, limit: int) -> list[dict]:
    n_companies = func.count(func.distinct(CompanyDocument.company_id))
    rows = db.execute(
        select(
            CompanyDocument.custom_label_norm,
            func.max(CompanyDocument.custom_label),
            n_companies,
            func.count(CompanyDocument.id),
        )
        .where(
            CompanyDocument.document_type_id.is_(None),
            CompanyDocument.custom_label_norm.is_not(None),
            CompanyDocument.status != "superseded",
        )
        .group_by(CompanyDocument.custom_label_norm)
        .having(n_companies >= min_companies)
        .order_by(n_companies.desc(), func.count(CompanyDocument.id).desc())
        .limit(limit)
    ).all()
    return [
        {"label_norm": norm, "label": label, "companies": companies, "documents": docs}
        for norm, label, companies, docs in rows
    ]
