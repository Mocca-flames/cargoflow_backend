from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.deps import get_current_user
from app.core.security import hash_password
from app.features.companies import service as company_service
from app.features.companies.models import ClientProfile, Company, CompanyRole
from app.features.documents.models import CompanyDocument, DocumentType
from app.features.documents.seed import seed_document_types
from app.features.documents.service import review_document
from app.features.users.model import User
from app.main import app

CLIENT_DOC_CODES = ("business_registration", "proof_of_address", "proof_of_goods", "director_id")


def make_company(db, roles=("client",), country="ZA", status="unverified", reg="REG-1"):
    c = Company(legal_name="Test Co", registration_number=reg, country_code=country, status=status)
    db.add(c)
    db.flush()
    for r in roles:
        db.add(CompanyRole(company_id=c.id, role=r))
    db.commit()
    return c


def make_user(db, email, staff_role="user", company_id=None, phone="+27820000099"):
    u = User(
        email=email,
        phone=phone,
        full_name="Test User",
        password_hash=hash_password("password123"),
        company_id=company_id,
        staff_role=staff_role,
    )
    db.add(u)
    db.commit()
    return u


def make_doc(db, company_id, type_id, uploader_id):
    doc = CompanyDocument(
        company_id=company_id,
        document_type_id=type_id,
        file_path=f"docs/{type_id}.pdf",
        original_filename="doc.pdf",
        content_type="application/pdf",
        size_bytes=10,
        status="pending",
        uploaded_by=uploader_id,
    )
    db.add(doc)
    db.commit()
    return doc


def client_type(db, code):
    return db.scalar(
        select(DocumentType).where(
            DocumentType.code == code,
            DocumentType.applies_to == "client",
            DocumentType.country_code.is_(None),
        )
    )


def test_seed_creates_4_client_doc_types_with_null_country_and_is_idempotent(db):
    created_first = seed_document_types(db)
    client_types = db.scalars(select(DocumentType).where(DocumentType.applies_to == "client")).all()
    assert {t.code for t in client_types} == set(CLIENT_DOC_CODES)
    assert len(client_types) == 4
    assert all(t.country_code is None for t in client_types)
    assert all(t.is_required for t in client_types)
    assert all(not t.requires_expiry for t in client_types)
    assert created_first >= 4

    created_second = seed_document_types(db)
    assert created_second == 0
    count = db.scalar(select(func.count(DocumentType.id)).where(DocumentType.applies_to == "client"))
    assert count == 4


def test_zw_client_sees_4_required_docs_in_missing_documents(db):
    seed_document_types(db)
    c = make_company(db, roles=("client",), country="ZW")
    missing = company_service._missing_documents(db, c)
    assert len(missing) == 4
    assert any("Business registration certificate" in m for m in missing)
    assert any("Proof of premises address" in m for m in missing)
    assert any("Proof of goods" in m for m in missing)
    assert any("Director ID document" in m for m in missing)


def test_approving_client_document_does_not_auto_verify(db):
    seed_document_types(db)
    c = make_company(db, roles=("client",), country="ZA")
    admin = make_user(db, email="admin1@example.com", staff_role="admin")
    doc = make_doc(db, c.id, client_type(db, "business_registration").id, admin.id)

    review_document(db, admin, doc.id, "approved", None)

    db.refresh(c)
    assert c.status == "unverified"
    assert c.verified_at is None


def test_verify_company_409_without_docs_then_verified_after_all_approved(db):
    seed_document_types(db)
    c = make_company(db, roles=("client",), country="ZA")
    admin = make_user(db, email="admin2@example.com", staff_role="admin")

    with pytest.raises(HTTPException) as exc:
        company_service.verify_company(db, c.id, admin)
    assert exc.value.status_code == 409

    for code in CLIENT_DOC_CODES:
        doc = make_doc(db, c.id, client_type(db, code).id, admin.id)
        review_document(db, admin, doc.id, "approved", None)

    db.refresh(c)
    assert c.status == "unverified"  # doc approval alone must not verify a client

    out = company_service.verify_company(db, c.id, admin)
    assert out.status == "verified"
    assert out.verified_at is not None


def test_transporter_document_approval_still_auto_verifies(db):
    seed_document_types(db)
    c = make_company(db, roles=("transporter",), country="ZA")
    admin = make_user(db, email="admin3@example.com", staff_role="admin")
    types = db.scalars(
        select(DocumentType).where(
            DocumentType.applies_to == "transporter",
            DocumentType.country_code == "ZA",
            DocumentType.is_required.is_(True),
        )
    ).all()
    assert types
    for dt in types:
        doc = make_doc(db, c.id, dt.id, admin.id)
        if dt.requires_expiry:
            review_document(db, admin, doc.id, "approved", None, expiry_date=date.today() + timedelta(days=30))
        else:
            review_document(db, admin, doc.id, "approved", None)

    db.refresh(c)
    assert c.status == "verified"
    assert c.verified_at is not None


def test_auth_me_returns_company_roles(client, db):
    c = make_company(db, roles=("client",))
    u = make_user(db, email="client@example.com", company_id=c.id)
    app.dependency_overrides[get_current_user] = lambda: u
    try:
        resp = client.get("/auth/me")
        assert resp.status_code == 200, resp.text
        assert resp.json()["company_roles"] == ["client"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    u2 = make_user(db, email="nocompany@example.com", company_id=None, phone="+27820000098")
    app.dependency_overrides[get_current_user] = lambda: u2
    try:
        resp = client.get("/auth/me")
        assert resp.status_code == 200, resp.text
        assert resp.json()["company_roles"] == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_company_detail_returns_client_block(db):
    c = make_company(db, roles=("client",))
    declared_at = datetime.now(timezone.utc)
    db.add(ClientProfile(
        company_id=c.id,
        premises_type="winery",
        goods_description="Bottled wine in cases",
        province="Western Cape",
        postal_code="8001",
        owns_goods_declared_at=declared_at,
    ))
    db.commit()

    detail = company_service.get_company_detail(db, c.id)
    assert detail.client is not None
    assert detail.client.premises_type == "winery"
    assert detail.client.goods_description == "Bottled wine in cases"
    assert detail.client.province == "Western Cape"
    assert detail.client.postal_code == "8001"
    assert detail.client.owns_goods_declared_at is not None

    c2 = make_company(db, roles=("broker",), reg="REG-2")
    detail2 = company_service.get_company_detail(db, c2.id)
    assert detail2.client is None
