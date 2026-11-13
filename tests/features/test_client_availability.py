from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.deps import get_current_user
from app.core.security import hash_password
from app.features.availability.models import TruckAvailability
from app.features.companies.models import Company, CompanyRole
from app.features.trucks.models import Truck
from app.features.users.model import User
from app.main import app


def make_company(db, roles, reg, status="verified"):
    c = Company(legal_name="Co", registration_number=reg, country_code="ZA", status=status)
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


def make_board_entry(db, reg="TRK-1"):
    c = make_company(db, ("transporter",), reg="REG-" + reg)
    truck = Truck(
        company_id=c.id,
        registration_number=reg,
        truck_type="superlink",
        capacity_tons=Decimal("34"),
    )
    db.add(truck)
    db.flush()
    av = TruckAvailability(
        truck_id=truck.id,
        status="available",
        location="Lusaka",
        available_from=date.today(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(av)
    db.commit()
    return av


def test_client_get_availability_returns_403(client, db):
    c = make_company(db, ("client",), reg="REG-C")
    u = make_user(db, "client@example.com", company_id=c.id)
    as_user(u)
    resp = client.get("/availability")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Not available for client accounts."


def test_transporter_get_availability_200_with_all_entries(client, db):
    make_board_entry(db, reg="TRK-T")
    c = make_company(db, ("transporter",), reg="REG-T2")
    u = make_user(db, "transp@example.com", company_id=c.id, phone="+27820000002")
    as_user(u)
    resp = client.get("/availability")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_broker_get_availability_200(client, db):
    make_board_entry(db, reg="TRK-B")
    c = make_company(db, ("broker",), reg="REG-B")
    u = make_user(db, "broker@example.com", company_id=c.id, phone="+27820000003")
    as_user(u)
    resp = client.get("/availability")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_staff_get_availability_200(client, db):
    make_board_entry(db, reg="TRK-S")
    admin = make_user(db, "admin@example.com", staff_role="admin", phone="+27820000004")
    as_user(admin)
    resp = client.get("/availability")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_user_without_company_get_availability_unchanged(client, db):
    make_board_entry(db, reg="TRK-N")
    u = make_user(db, "nocompany@example.com", company_id=None, phone="+27820000005")
    as_user(u)
    resp = client.get("/availability")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1
