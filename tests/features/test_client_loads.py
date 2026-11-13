from decimal import Decimal

from app.core.deps import get_current_user
from app.core.security import hash_password
from app.features.companies.models import Company, CompanyRole
from app.features.loads.models import Load
from app.features.users.model import User
from app.main import app


def make_company(db, roles=("client",), status="verified", country="ZA", reg="REG-C1"):
    c = Company(legal_name="Co", registration_number=reg, country_code=country, status=status)
    db.add(c)
    db.flush()
    for r in roles:
        db.add(CompanyRole(company_id=c.id, role=r))
    db.commit()
    return c


def make_user(db, email, staff_role="user", company_id=None, phone="+27820000001"):
    u = User(
        email=email,
        phone=phone,
        full_name="U",
        password_hash=hash_password("password123"),
        company_id=company_id,
        staff_role=staff_role,
    )
    db.add(u)
    db.commit()
    return u


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def load_body(**overrides):
    body = {
        "origin": "Lusaka",
        "destination": "Harare",
        "commodity": "Maize",
        "truck_type": "superlink",
        "trucks_needed": 2,
        "rate": "12000.00",
        "currency": "ZAR",
    }
    body.update(overrides)
    return body


def make_load(db, company_id, origin="Lusaka", posted_as=None):
    load = Load(
        origin=origin,
        destination="Harare",
        commodity="Maize",
        trucks_needed=1,
        rate=Decimal("100"),
        currency="ZAR",
        company_id=company_id,
        posted_as=posted_as,
    )
    db.add(load)
    db.commit()
    return load


def test_verified_client_can_create_load(client, db):
    c = make_company(db, roles=("client",), status="verified")
    u = make_user(db, "client1@example.com", company_id=c.id)
    as_user(u)
    resp = client.post("/loads", json=load_body())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["posted_as"] == "client"
    assert data["company_id"] == c.id


def test_unverified_client_gets_409(client, db):
    c = make_company(db, roles=("client",), status="unverified")
    u = make_user(db, "client2@example.com", company_id=c.id, phone="+27820000002")
    as_user(u)
    resp = client.post("/loads", json=load_body())
    assert resp.status_code == 409


def test_transporter_gets_403(client, db):
    c = make_company(db, roles=("transporter",), status="verified", reg="REG-T1")
    u = make_user(db, "transp@example.com", company_id=c.id, phone="+27820000003")
    as_user(u)
    resp = client.post("/loads", json=load_body())
    assert resp.status_code == 403
    assert "Only brokers and clients can post loads." in resp.text


def test_broker_can_still_create_load(client, db):
    c = make_company(db, roles=("broker",), status="verified", reg="REG-B1")
    u = make_user(db, "broker@example.com", company_id=c.id, phone="+27820000004")
    as_user(u)
    resp = client.post("/loads", json=load_body())
    assert resp.status_code == 201, resp.text
    assert resp.json()["posted_as"] == "broker"
    assert resp.json()["company_id"] == c.id


def test_client_company_id_in_body_is_ignored(client, db):
    c = make_company(db, roles=("client",), status="verified")
    other = make_company(db, roles=("broker",), reg="REG-B2")
    u = make_user(db, "client3@example.com", company_id=c.id, phone="+27820000005")
    as_user(u)
    resp = client.post("/loads", json=load_body(company_id=other.id))
    assert resp.status_code == 201, resp.text
    assert resp.json()["company_id"] == c.id


def test_client_list_loads_returns_only_own(client, db):
    c = make_company(db, roles=("client",), status="verified")
    other = make_company(db, roles=("broker",), reg="REG-B3")
    make_load(db, c.id, origin="Lusaka")
    make_load(db, other.id, origin="Harare")
    u = make_user(db, "client4@example.com", company_id=c.id, phone="+27820000006")
    as_user(u)
    resp = client.get("/loads")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["company_id"] == c.id


def test_client_get_load_404_for_other_company_200_for_own(client, db):
    c = make_company(db, roles=("client",), status="verified")
    other = make_company(db, roles=("broker",), reg="REG-B4")
    own = make_load(db, c.id)
    foreign = make_load(db, other.id)
    u = make_user(db, "client5@example.com", company_id=c.id, phone="+27820000007")
    as_user(u)
    assert client.get(f"/loads/{foreign.id}").status_code == 404
    resp = client.get(f"/loads/{own.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == own.id


def test_broker_and_transporter_still_see_all_loads(client, db):
    c = make_company(db, roles=("client",), status="verified")
    other = make_company(db, roles=("broker",), reg="REG-B5")
    make_load(db, c.id, origin="Lusaka")
    make_load(db, other.id, origin="Harare")

    broker_user = make_user(db, "broker2@example.com", company_id=other.id, phone="+27820000008")
    as_user(broker_user)
    rows = client.get("/loads").json()
    assert len(rows) == 2

    t = make_company(db, roles=("transporter",), reg="REG-T2")
    transp_user = make_user(db, "transp2@example.com", company_id=t.id, phone="+27820000009")
    as_user(transp_user)
    rows = client.get("/loads").json()
    assert len(rows) == 2


def test_staff_post_for_client_company_is_tagged_client(client, db):
    c = make_company(db, roles=("client",), status="verified")
    admin = make_user(db, "admin@example.com", staff_role="admin", phone="+27820000010")
    as_user(admin)
    resp = client.post("/loads", json=load_body(company_id=c.id))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["posted_as"] == "client"
    assert data["company_id"] == c.id


def test_public_loads_exposes_posted_as_and_no_company_id(client, db):
    c = make_company(db, roles=("client",), status="verified")
    make_load(db, c.id, posted_as="client")
    resp = client.get("/public/loads")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["posted_as"] == "client"
    assert "company_id" not in rows[0]


def test_client_cannot_patch_or_delete_other_company_load(client, db):
    c = make_company(db, roles=("client",), status="verified")
    other = make_company(db, roles=("broker",), reg="REG-B6")
    foreign = make_load(db, other.id)
    u = make_user(db, "client6@example.com", company_id=c.id, phone="+27820000011")
    as_user(u)
    assert client.patch(f"/loads/{foreign.id}", json={"note": "x"}).status_code == 404
    assert client.delete(f"/loads/{foreign.id}").status_code == 404
