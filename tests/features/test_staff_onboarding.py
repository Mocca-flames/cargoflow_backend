import pytest

from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.features.companies.models import Company, CompanyRole, TransporterProfile
from app.features.onboarding.schemas import StaffOnboardingIn
from app.features.users.model import User
from app.main import app

from tests.features.test_companies_list import as_user, make_admin


def _client_body(**overrides) -> dict:
    body = {
        "company": {
            "legal_name": "Staff Made Foods (Pty) Ltd",
            "registration_number": "2024/000101",
            "country_code": "ZA",
            "phone": "+27820101001",
        },
        "roles": ["client"],
        "client": {
            "premises_type": "factory",
            "goods_description": "Palletised maize flour, 1 ton bags",
            "street_address": "12 Industrial Road",
            "city": "Johannesburg",
            "province": "Gauteng",
            "postal_code": "2001",
            "owns_goods": True,
        },
        "create_owner": True,
        "owner": {"full_name": "Owner One", "email": "staff-owner@example.com", "phone": "+27820101001"},
    }
    body.update(overrides)
    return body


def test_staff_submit_with_manual_password(client, db):
    as_user(make_admin(db, "staff-admin1@example.com", "+27820900001"))

    body = _client_body(owner_password="S3curePass!23")
    resp = client.post("/onboarding/staff-submit", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "unverified"
    assert data["roles"] == ["client"]

    user = db.query(User).filter(User.email == "staff-owner@example.com").one()
    assert user.company_id == data["company_id"]
    assert verify_password("S3curePass!23", user.password_hash)
    assert user.must_change_password is False
    assert user.created_by is not None

    company = db.get(Company, data["company_id"])
    roles = {r.role for r in db.query(CompanyRole).filter(CompanyRole.company_id == company.id).all()}
    assert roles == {"client"}


def test_staff_submit_temp_password_flow(client, db):
    as_user(make_admin(db, "staff-admin2@example.com", "+27820900002"))

    body = _client_body(
        registration_number="2024/000102",
        company_phone="+27820101002",
    )
    body["owner"] = {"full_name": "Owner Two", "email": "staff-owner2@example.com", "phone": "+27820101002"}
    resp = client.post("/onboarding/staff-submit", json=body)
    assert resp.status_code == 201, resp.text

    user = db.query(User).filter(User.email == "staff-owner2@example.com").one()
    assert user.must_change_password is True


def test_staff_submit_transporter_with_manual_password(client, db):
    as_user(make_admin(db, "staff-admin3@example.com", "+27820900003"))

    body = {
        "company": {
            "legal_name": "Staff Haulage (Pty) Ltd",
            "registration_number": "2024/000103",
            "country_code": "ZA",
        },
        "roles": ["transporter"],
        "transporter": {"operating_countries": ["ZA"]},
        "create_owner": True,
        "owner_password": "Another1Pass",
        "owner": {"full_name": "Owner Three", "email": "staff-owner3@example.com", "phone": "+27820101003"},
    }
    resp = client.post("/onboarding/staff-submit", json=body)
    assert resp.status_code == 201, resp.text

    company = db.get(Company, resp.json()["company_id"])
    profile = db.query(TransporterProfile).filter(TransporterProfile.company_id == company.id).one()
    assert profile.operating_countries == ["ZA"]

    user = db.query(User).filter(User.email == "staff-owner3@example.com").one()
    assert verify_password("Another1Pass", user.password_hash)


def test_owner_password_requires_create_owner(client, db):
    body = _client_body(create_owner=False, owner_password="S3curePass!23")
    with pytest.raises(Exception):
        StaffOnboardingIn(**body)


def test_owner_password_without_owner_rejected(client):
    body = _client_body(create_owner=True, owner_password="S3curePass!23")
    del body["owner"]
    resp = client.post("/onboarding/staff-submit", json=body)
    assert resp.status_code == 422


def test_short_owner_password_rejected(client):
    body = _client_body(owner_password="short")
    resp = client.post("/onboarding/staff-submit", json=body)
    assert resp.status_code == 422


def test_staff_submit_requires_admin_or_director(client, db):
    user = User(
        email="plain@example.com",
        phone="+27820900010",
        full_name="Plain User",
        password_hash=hash_password("password123"),
        staff_role="user",
    )
    db.add(user)
    db.commit()
    as_user(user)

    resp = client.post("/onboarding/staff-submit", json=_client_body())
    assert resp.status_code == 403


def test_staff_submit_requires_auth(client):
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.post("/onboarding/staff-submit", json=_client_body())
    assert resp.status_code in (401, 403)
