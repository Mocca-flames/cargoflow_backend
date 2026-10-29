from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.companies.models import Company, CompanyRole
from app.features.loads.models import Load
from app.features.loads.schemas import LoadCreate, LoadUpdate
from app.features.users.model import User

STAFF_ROLES = ("admin", "director")


def _is_staff(user: User) -> bool:
    return user.staff_role in STAFF_ROLES


def create_load(db: Session, body: LoadCreate, user: User) -> Load:
    if _is_staff(user):
        company_id = body.company_id
        if company_id is not None and not db.get(Company, company_id):
            raise HTTPException(404, "Company not found.")
    else:
        if not user.company_id:
            raise HTTPException(403, "Your account has no company.")
        company = db.get(Company, user.company_id)
        roles = set(db.scalars(select(CompanyRole.role).where(CompanyRole.company_id == company.id)))
        if "broker" not in roles:
            raise HTTPException(403, "Only brokers can post loads.")
        if company.status != "verified":
            raise HTTPException(409, "Company is not verified yet.")
        company_id = company.id

    data = body.model_dump(exclude={"company_id"})
    load = Load(**data, company_id=company_id, posted_by=user.id)
    db.add(load)
    db.commit()
    db.refresh(load)
    return load


def list_loads(
    db: Session,
    status: str | None,
    origin: str | None,
    destination: str | None,
    truck_type: str | None,
    limit: int,
    offset: int,
) -> list[Load]:
    q = select(Load).order_by(Load.created_at.desc(), Load.id.desc())
    if status:
        q = q.where(Load.status == status)
    if origin:
        q = q.where(Load.origin.ilike(f"%{origin.strip()}%"))
    if destination:
        q = q.where(Load.destination.ilike(f"%{destination.strip()}%"))
    if truck_type:
        q = q.where(Load.truck_type == truck_type)
    return list(db.scalars(q.limit(limit).offset(offset)).all())


def get_load(db: Session, load_id: int) -> Load:
    load = db.get(Load, load_id)
    if not load:
        raise HTTPException(404, "Load not found.")
    return load


def update_load(db: Session, load_id: int, body: LoadUpdate, user: User) -> Load:
    load = get_load(db, load_id)
    if not _is_staff(user) and (load.company_id is None or load.company_id != user.company_id):
        raise HTTPException(404, "Load not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(load, field, value)
    db.commit()
    db.refresh(load)
    return load


def get_open_load(db: Session, load_id: int) -> Load:
    load = get_load(db, load_id)
    if load.status != "open":
        raise HTTPException(404, "Load not found.")
    return load
