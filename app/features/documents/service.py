from datetime import date, datetime, time, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.storage import LocalStorage, StorageError, storage_error_to_http
from app.features.companies.models import Company, CompanyRole
from app.features.documents.models import CompanyDocument, DocumentType
from app.features.users.model import User

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
            or doc_type.applies_to not in roles
            or doc_type.applies_to == "truck"  # truck documents come in Step 6
            or (doc_type.country_code and doc_type.country_code != company.country_code)
        ):
            raise HTTPException(400, "Invalid document type for this company")
        requires_expiry = doc_type.requires_expiry
    else:
        label = (custom_label or "").strip()[:150]
        if not label:
            raise HTTPException(400, "custom_label is required for other documents")
        label_norm = " ".join(label.lower().split())

    # 3. Expiry
    expiry_dt = None
    if expiry_date is not None:
        expiry_dt = datetime.combine(expiry_date, time.min, tzinfo=timezone.utc)
        if expiry_dt < datetime.now(timezone.utc):
            raise HTTPException(400, "Expiry date is in the past")
    elif requires_expiry:
        raise HTTPException(400, "expiry_date is required for this document type")

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
                CompanyDocument.truck_id.is_(None),
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