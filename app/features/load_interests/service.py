from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.load_interests.models import LoadInterest
from app.features.load_interests.schemas import (
    ConvertLeadIn,
    InterestCreate,
    InterestOut,
    InterestReceived,
    InterestUpdate,
)
from app.features.loads.models import Load
from app.core.email import BrevoMailer
from app.features.onboarding.schemas import OnboardingOut, OwnerIn, StaffOnboardingIn
from app.features.onboarding.service import staff_submit
from app.features.users.model import User


def _received() -> InterestReceived:
    return InterestReceived(message="Thank you. We will call you soon about this load.")


def _out(interest: LoadInterest, load: Load) -> InterestOut:
    return InterestOut(
        id=interest.id,
        load_id=interest.load_id,
        load_origin=load.origin,
        load_destination=load.destination,
        full_name=interest.full_name,
        phone=interest.phone,
        truck_type=interest.truck_type,
        status=interest.status,
        company_id=interest.company_id,
        note=interest.note,
        created_at=interest.created_at,
        handled_at=interest.handled_at,
    )


def submit_interest(db: Session, load_id: int, body: InterestCreate) -> InterestReceived:
    load = db.get(Load, load_id)
    if not load or load.status != "open":
        raise HTTPException(404, "Load not found.")
    if body.website:  # honeypot: pretend success, store nothing
        return _received()
    exists = db.scalar(
        select(LoadInterest.id).where(
            LoadInterest.load_id == load_id, LoadInterest.phone == body.phone
        )
    )
    if exists:  # same person tapping twice: same friendly answer
        return _received()
    db.add(
        LoadInterest(
            load_id=load_id,
            full_name=body.full_name,
            phone=body.phone,
            truck_type=body.truck_type,
            consent=True,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # lost a race with an identical submit
    return _received()


def list_interests(
    db: Session, status: str | None, load_id: int | None, limit: int, offset: int
) -> list[InterestOut]:
    q = (
        select(LoadInterest, Load)
        .join(Load, Load.id == LoadInterest.load_id)
        .order_by(LoadInterest.created_at.desc(), LoadInterest.id.desc())
    )
    if status:
        q = q.where(LoadInterest.status == status)
    if load_id:
        q = q.where(LoadInterest.load_id == load_id)
    rows = db.execute(q.limit(limit).offset(offset)).all()
    return [_out(i, l) for i, l in rows]


def update_interest(db: Session, interest_id: int, body: InterestUpdate, admin: User) -> InterestOut:
    interest = db.get(LoadInterest, interest_id)
    if not interest:
        raise HTTPException(404, "Interest not found.")
    if body.status is not None:
        interest.status = body.status
        interest.handled_by = admin.id
        interest.handled_at = datetime.now(timezone.utc)
    if body.note is not None:
        interest.note = body.note
    db.commit()
    db.refresh(interest)
    return _out(interest, db.get(Load, interest.load_id))


def convert_interest(
    db: Session, interest_id: int, body: ConvertLeadIn, admin: User, mailer: BrevoMailer
) -> OnboardingOut:
    lead = db.get(LoadInterest, interest_id)
    if not lead:
        raise HTTPException(404, "Interest not found.")
    if lead.status == "onboarded" or lead.company_id is not None:
        raise HTTPException(409, "This lead has already been onboarded.")
    owner = None
    if body.create_owner:
        owner = OwnerIn(full_name=lead.full_name, email=body.owner_email, phone=lead.phone)
    staff_body = StaffOnboardingIn(
        company=body.company,
        roles=body.roles,
        transporter=body.transporter,
        broker=body.broker,
        owner=owner,
        create_owner=body.create_owner,
    )
    result = staff_submit(db, staff_body, admin, mailer)
    lead.company_id = result.company_id
    lead.status = "onboarded"
    lead.handled_by = admin.id
    lead.handled_at = datetime.now(timezone.utc)
    db.commit()
    return result
