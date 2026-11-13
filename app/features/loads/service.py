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


def _company_roles(db: Session, company_id: int) -> set[str]:
    return set(db.scalars(select(CompanyRole.role).where(CompanyRole.company_id == company_id)))


def _posted_as(roles: set[str]) -> str:
    if "client" in roles:
        return "client"
    if "broker" in roles:
        return "broker"
    return "staff"


def client_scope(db: Session, user: User) -> int | None:
    """Company id whose loads a client user may see; None means full board (staff, brokers, transporters)."""
    if _is_staff(user) or not user.company_id:
        return None
    if "client" in _company_roles(db, user.company_id):
        return user.company_id
    return None


def create_load(db: Session, body: LoadCreate, user: User) -> Load:
    if _is_staff(user):
        company_id = body.company_id
        if company_id is not None and not db.get(Company, company_id):
            raise HTTPException(404, "Company not found.")
        posted_as = _posted_as(_company_roles(db, company_id)) if company_id is not None else "staff"
    else:
        if not user.company_id:
            raise HTTPException(403, "Your account has no company.")
        company = db.get(Company, user.company_id)
        roles = _company_roles(db, company.id)
        if not ({"broker", "client"} & roles):
            raise HTTPException(403, "Only brokers and clients can post loads.")
        if company.status != "verified":
            raise HTTPException(409, "Company is not verified yet.")
        company_id = company.id
        posted_as = _posted_as(roles)

    data = body.model_dump(exclude={"company_id"})
    load = Load(**data, company_id=company_id, posted_by=user.id, posted_as=posted_as)
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
    company_id: int | None = None,
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
    if company_id is not None:
        q = q.where(Load.company_id == company_id)
    return list(db.scalars(q.limit(limit).offset(offset)).all())


def get_load(db: Session, load_id: int) -> Load:
    load = db.get(Load, load_id)
    if not load:
        raise HTTPException(404, "Load not found.")
    return load


def get_load_for_user(db: Session, load_id: int, user: User) -> Load:
    load = get_load(db, load_id)
    scope = client_scope(db, user)
    if scope is not None and load.company_id != scope:
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


def delete_load(db: Session, load_id: int, user: User) -> None:
    load = get_load(db, load_id)
    if not _is_staff(user) and (load.company_id is None or load.company_id != user.company_id):
        raise HTTPException(404, "Load not found.")
    db.delete(load)
    db.commit()


def get_open_load(db: Session, load_id: int) -> Load:
    load = get_load(db, load_id)
    if load.status != "open":
        raise HTTPException(404, "Load not found.")
    return load
