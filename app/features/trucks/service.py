from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.features.companies.models import Company
from app.features.documents.models import CompanyDocument, DocumentType
from app.features.trucks.models import Truck
from app.features.trucks.schemas import TruckCreate, TruckDetail, TruckOut, TruckUpdate
from app.features.users.model import User

STAFF_ROLES = ("admin", "director")


def _is_staff(user: User) -> bool:
    return user.staff_role in STAFF_ROLES


def _get_truck(db: Session, truck_id: int, user: User) -> Truck:
    truck = db.get(Truck, truck_id)
    if not truck or (not _is_staff(user) and truck.company_id != user.company_id):
        raise HTTPException(404, "Truck not found.")
    return truck


def create_truck(db: Session, body: TruckCreate, user: User) -> Truck:
    if _is_staff(user):
        if not body.company_id:
            raise HTTPException(422, "company_id is required.")
        company_id = body.company_id
    else:
        if not user.company_id:
            raise HTTPException(403, "Your account has no company.")
        company_id = user.company_id

    company = db.scalar(
        select(Company).options(selectinload(Company.roles)).where(Company.id == company_id)
    )
    if not company:
        raise HTTPException(404, "Company not found.")
    if "transporter" not in [r.role for r in company.roles]:
        raise HTTPException(409, "Company is not a transporter.")

    reg = "".join(body.registration_number.split()).upper()
    if db.scalar(select(Truck.id).where(Truck.registration_number == reg)):
        raise HTTPException(409, "A truck with this registration number already exists.")

    truck = Truck(
        company_id=company_id,
        registration_number=reg,
        truck_type=body.truck_type,
        capacity_tons=body.capacity_tons,
        created_by=user.id,
    )
    db.add(truck)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A truck with this registration number already exists.")
    db.refresh(truck)
    return truck


def list_trucks(
    db: Session, user: User, company_id: int | None, active: bool | None, limit: int, offset: int
) -> list[Truck]:
    q = select(Truck).order_by(Truck.created_at.desc())
    if _is_staff(user):
        if company_id:
            q = q.where(Truck.company_id == company_id)
    else:
        q = q.where(Truck.company_id == user.company_id)
    if active is not None:
        q = q.where(Truck.is_active == active)
    return list(db.scalars(q.limit(limit).offset(offset)).all())


def update_truck(db: Session, truck_id: int, body: TruckUpdate, user: User) -> Truck:
    truck = _get_truck(db, truck_id, user)
    if body.registration_number is not None:
        if not _is_staff(user):
            raise HTTPException(403, "Only an admin can change the registration number.")
        reg = "".join(body.registration_number.split()).upper()
        if reg != truck.registration_number and db.scalar(select(Truck.id).where(Truck.registration_number == reg)):
            raise HTTPException(409, "A truck with this registration number already exists.")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field != "capacity_tons":
            continue
        setattr(truck, field, value)
    db.commit()
    db.refresh(truck)
    return truck


def _missing_truck_documents(db: Session, truck: Truck) -> list[str]:
    company = db.get(Company, truck.company_id)
    types = db.scalars(
        select(DocumentType).where(
            DocumentType.is_active.is_(True),
            DocumentType.is_required.is_(True),
            DocumentType.applies_to == "truck",
            (DocumentType.country_code == company.country_code) | (DocumentType.country_code.is_(None)),
        )
    ).all()
    approved_ids = set(db.scalars(
        select(CompanyDocument.document_type_id).where(
            CompanyDocument.truck_id == truck.id,
            CompanyDocument.status == "approved",
        )
    ).all())
    return sorted({t.name for t in types if t.id not in approved_ids})


def get_truck(db: Session, truck_id: int, user: User) -> TruckDetail:
    truck = _get_truck(db, truck_id, user)
    missing = _missing_truck_documents(db, truck)
    return TruckDetail(
        **TruckOut.model_validate(truck).model_dump(),
        docs_complete=not missing,
        missing=missing,
    )
