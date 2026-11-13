from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.features.companies.models import ClientProfile, Company, CompanyRole
from app.features.onboarding.schemas import OnboardingSubmitIn

TEST_DB = "cargo_flow_test"


def _url(db_name: str) -> str:
    base = settings.DATABASE_URL.rpartition("/")[0]
    return f"{base}/{db_name}"


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(_url("postgres"))
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        exists = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB}'")).scalar()
        if not exists:
            conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    admin.dispose()
    eng = create_engine(_url(TEST_DB))
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(email: str) -> str:
    payload = {"sub": email, "type": "onboarding", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _client_body(**overrides) -> dict:
    body = {
        "company": {
            "legal_name": "Acme Factory (Pty) Ltd",
            "registration_number": "2024/000001",
            "country_code": "ZA",
            "phone": "+27820000001",
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
        "token": _token("owner@example.com"),
        "password": "password123",
        "owner": {"full_name": "Owner One", "email": "owner@example.com", "phone": "+27820000001"},
    }
    body.update(overrides)
    return body


def _broker_profile():
    return {"corridors": ["ZA-ZM"], "finds_trucks": True}


def _transporter_profile():
    return {"operating_countries": ["ZA"]}


def test_client_plus_broker_roles_rejected(client):
    body = _client_body(roles=["client", "broker"], broker=_broker_profile())
    resp = client.post("/onboarding/submit", json=body)
    assert resp.status_code == 422


def test_client_plus_transporter_roles_rejected(client):
    body = _client_body(roles=["client", "transporter"], transporter=_transporter_profile())
    resp = client.post("/onboarding/submit", json=body)
    assert resp.status_code == 422


def test_client_role_without_client_profile_rejected(client):
    body = _client_body()
    del body["client"]
    resp = client.post("/onboarding/submit", json=body)
    assert resp.status_code == 422


def test_client_profile_with_non_client_role_rejected(client):
    body = _client_body(roles=["broker"], broker=_broker_profile())
    resp = client.post("/onboarding/submit", json=body)
    assert resp.status_code == 422


def test_owns_goods_false_rejected(client):
    body = _client_body()
    body["client"]["owns_goods"] = False
    resp = client.post("/onboarding/submit", json=body)
    assert resp.status_code == 422


def test_valid_client_signup_creates_company_address_and_client_profile(client, db):
    resp = client.post("/onboarding/submit", json=_client_body())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["roles"] == ["client"]
    assert data["status"] == "unverified"

    company = db.query(Company).filter(Company.registration_number == "2024/000001").one()
    assert company.address == "12 Industrial Road"
    assert company.city == "Johannesburg"

    roles = {r.role for r in db.query(CompanyRole).filter(CompanyRole.company_id == company.id).all()}
    assert roles == {"client"}

    profile = db.query(ClientProfile).filter(ClientProfile.company_id == company.id).one()
    assert profile.premises_type == "factory"
    assert profile.goods_description == "Palletised maize flour, 1 ton bags"
    assert profile.province == "Gauteng"
    assert profile.postal_code == "2001"
    assert profile.owns_goods_declared_at is not None
    assert profile.owns_goods_declared_at.tzinfo is not None


def test_transporter_and_broker_payloads_still_validate():
    transporter_body = _client_body(
        roles=["transporter"],
        transporter=_transporter_profile(),
    )
    del transporter_body["client"]
    OnboardingSubmitIn(**transporter_body)

    broker_body = _client_body(roles=["broker"], broker=_broker_profile())
    del broker_body["client"]
    OnboardingSubmitIn(**broker_body)
