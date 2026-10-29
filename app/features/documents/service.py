from datetime import date, datetime, time, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session


from app.core.storage import LocalStorage, StorageError, storage_error_to_http
from app.features.companies.models import Company, CompanyRole
from app.features.documents.models import CompanyDocument, DocumentType
from app.features.users.model import User
from app.features.trucks.models import Truck
from app.features.companies import service as company_service

STAFF = {"admin", "director"}


def upload_document(
    db: Session,
    storage: LocalStorage,
    user: User,
    file: UploadFile,
    document_type_id: int | None,
    company_id: int | None,
    expiry_date: date | None,
    custom_label: str | None,
    truck_id: int | None = None,
) -> CompanyDocument:
    # 1. Which company?
    if user.staff_role in STAFF:
        if company_id is None:
            raise HTTPException(400, "company_id is required for staff uploads")
    else:
        if user.company_id is None or (company_id is not None and company_id != user.company_id):
            raise HTTPException(403, "Not allowed")
        company_id = user.company_id

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    roles = set(db.scalars(select(CompanyRole.role).where(CompanyRole.company_id == company.id)))
    if truck_id is not None:
        truck = db.get(Truck, truck_id)
        if not truck or truck.company_id != company.id:
            raise HTTPException(404, "Truck not found for this company")

    # 2. Which document type? (standard type, or "Other" with a label)
    doc_type = None
    label = None
    label_norm = None
    requires_expiry = False
    if document_type_id is not None:
        doc_type = db.get(DocumentType, document_type_id)
        if (
            not doc_type
            or not doc_type.is_active
            or (doc_type.applies_to != "truck" and doc_type.applies_to not in roles)
            or (doc_type.applies_to == "truck") != (truck_id is not None)
            or (doc_type.country_code and doc_type.country_code != company.country_code)
        ):
            raise HTTPException(400, "Invalid document type for this company")
        requires_expiry = doc_type.requires_expiry
    else:
        label = (custom_label or "").strip()[:150]
        if not label:
            raise HTTPException(400, "custom_label is required for other documents")
        label_norm = " ".join(label.lower().split())

    
    # 3. Expiry (optional at upload; required at approval for types that need it)
    expiry_dt = None
    if expiry_date is not None:
        expiry_dt = datetime.combine(expiry_date, time.min, tzinfo=timezone.utc)
        if expiry_dt < datetime.now(timezone.utc):
            raise HTTPException(400, "Expiry date is in the past")

    # 4. Save the file, then the DB row. Delete the file again if the DB fails.
    try:
        stored = storage.save(file, f"company_{company.id}")
    except StorageError as exc:
        raise storage_error_to_http(exc)

    try:
        same_doc = (
            CompanyDocument.document_type_id == document_type_id
            if document_type_id is not None
            else CompanyDocument.custom_label_norm == label_norm
        )
        db.execute(
            update(CompanyDocument)
            .where(
                CompanyDocument.company_id == company.id,
                CompanyDocument.truck_id == truck_id if truck_id is not None else CompanyDocument.truck_id.is_(None),
                CompanyDocument.status.in_(("pending", "approved")),
                same_doc,
            )
            .values(status="superseded")
        )
        doc = CompanyDocument(
            company_id=company.id,
            document_type_id=document_type_id,
            custom_label=label,
            custom_label_norm=label_norm,
            truck_id=truck_id,
            file_path=stored.relative_path,
            original_filename=stored.original_filename or "document",
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            expiry_date=expiry_dt,
            status="pending",
            uploaded_by=user.id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    except Exception:
        db.rollback()
        storage.delete(stored.relative_path)
        raise


def list_documents(
    db: Session,
    user: User,
    company_id: int | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[CompanyDocument]:
    stmt = select(CompanyDocument)

    if user.staff_role in STAFF:
        if company_id is not None:
            stmt = stmt.where(CompanyDocument.company_id == company_id)
    else:
        if user.company_id is None:
            return []
        stmt = stmt.where(CompanyDocument.company_id == user.company_id)

    if status:
        stmt = stmt.where(CompanyDocument.status == status)

    stmt = stmt.order_by(CompanyDocument.created_at.desc(), CompanyDocument.id.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def get_document_for_download(db: Session, storage: LocalStorage, user: User, doc_id: int):
    doc = db.get(CompanyDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if user.staff_role not in STAFF and doc.company_id != user.company_id:
        raise HTTPException(404, "Document not found")
    try:
        path = storage.open_path(doc.file_path)
    except StorageError:
        raise HTTPException(404, "Document not found")
    return doc, path

def review_document(db: Session, reviewer: User, doc_id: int, decision: str, note: str | None,
                    expiry_date: date | None = None) -> CompanyDocument:
    doc = db.scalar(select(CompanyDocument).where(CompanyDocument.id == doc_id).with_for_update())
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.status != "pending":
        raise HTTPException(409, f"Document is already {doc.status}")

    if decision == "approved":
        if expiry_date is not None:
            new_expiry = datetime.combine(expiry_date, time.min, tzinfo=timezone.utc)
            if new_expiry < datetime.now(timezone.utc):
                raise HTTPException(400, "Expiry date is in the past")
            doc.expiry_date = new_expiry
        if doc.expiry_date is None and doc.document_type_id is not None:
            dt = db.get(DocumentType, doc.document_type_id)
            if dt and dt.requires_expiry:
                raise HTTPException(400, "expiry_date is required to approve this document type")

    doc.status = decision
    doc.reviewed_by = reviewer.id
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.review_note = (note or "").strip() or None
    if decision == "approved" and doc.truck_id is None:
        db.flush()
        company = company_service._get_company(db, doc.company_id)
        if company.status == "unverified" and not company_service._missing_documents(db, company):
            company.status = "verified"
            company.verified_at = datetime.now(timezone.utc)
            company.verified_by = reviewer.id
            company.rejection_reason = None
    db.commit()
    db.refresh(doc)
    return doc