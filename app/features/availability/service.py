from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.features.availability.models import TruckAvailability
from app.features.availability.schemas import AvailabilityCreate, AvailabilityOut
from app.features.companies.models import Company
from app.features.trucks.models import Truck
from app.features.trucks.service import _missing_truck_documents
from app.features.users.model import User

STAFF_ROLES = ("admin", "director")


def _is_staff(user: User) -> bool:
    return user.staff_role in STAFF_ROLES


def _out(av: TruckAvailability, truck: Truck) -> AvailabilityOut:
    return AvailabilityOut(
        id=av.id,
        truck_id=truck.id,
        company_id=truck.company_id,
        registration_number=truck.registration_number,
        truck_type=truck.truck_type,
        capacity_tons=truck.capacity_tons,
        status=av.status,
        location=av.location,
        destination=av.destination,
        available_from=av.available_from,
        expires_at=av.expires_at,
        note=av.note,
        created_at=av.created_at,
    )


def post_availability(db: Session, body: AvailabilityCreate, user: User) -> AvailabilityOut:
    truck = db.get(Truck, body.truck_id)
    if not truck or (not _is_staff(user) and truck.company_id != user.company_id):
        raise HTTPException(404, "Truck not found.")
    if not truck.is_active:
        raise HTTPException(409, "Truck is not active.")
    company = db.get(Company, truck.company_id)
    if company.status != "verified":
        raise HTTPException(409, "Company is not verified yet.")
    missing = _missing_truck_documents(db, truck)
    if missing:
        raise HTTPException(409, "Missing approved truck documents: " + ", ".join(missing))

    now = datetime.now(timezone.utc)
    today = now.date()
    available_from = body.available_from or today
    if available_from < today:
        raise HTTPException(400, "available_from is in the past.")
    start = max(now, datetime.combine(available_from, time.min, tzinfo=timezone.utc))

    # A new post replaces the truck's previous open one.
    db.execute(
        update(TruckAvailability)
        .where(TruckAvailability.truck_id == truck.id, TruckAvailability.expires_at > now)
        .values(expires_at=now)
    )
    av = TruckAvailability(
        truck_id=truck.id,
        status=body.status,
        location=body.location,
        destination=body.destination,
        available_from=available_from,
        expires_at=start + timedelta(days=body.days_valid),
        note=body.note,
        created_by=user.id,
    )
    db.add(av)
    db.commit()
    db.refresh(av)
    return _out(av, truck)


def list_board(
    db: Session, status: str | None, location: str | None, limit: int, offset: int
) -> list[AvailabilityOut]:
    now = datetime.now(timezone.utc)
    q = (
        select(TruckAvailability, Truck)
        .join(Truck, Truck.id == TruckAvailability.truck_id)
        .where(TruckAvailability.expires_at > now, Truck.is_active.is_(True))
        .order_by(TruckAvailability.created_at.desc())
    )
    if status:
        q = q.where(TruckAvailability.status == status)
    if location:
        q = q.where(TruckAvailability.location.ilike(f"%{location.strip()}%"))
    rows = db.execute(q.limit(limit).offset(offset)).all()
    return [_out(av, truck) for av, truck in rows]


def withdraw(db: Session, availability_id: int, user: User) -> AvailabilityOut:
    av = db.get(TruckAvailability, availability_id)
    truck = db.get(Truck, av.truck_id) if av else None
    if not av or (not _is_staff(user) and truck.company_id != user.company_id):
        raise HTTPException(404, "Availability not found.")
    now = datetime.now(timezone.utc)
    if av.expires_at > now:
        av.expires_at = now
        db.commit()
        db.refresh(av)
    return _out(av, truck)
