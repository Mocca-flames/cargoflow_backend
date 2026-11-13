import html
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import BrevoMailer
from app.features.companies.models import Company, CompanyRole
from app.features.loads.models import Load
from app.features.loads.schemas import LoadCreate, LoadUpdate
from app.features.users.model import User

logger = logging.getLogger(__name__)

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


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else "-"


def _load_email_html(load: Load, company: Company | None, user: User) -> str:
    rows: list[tuple[str, str]] = [
        ("Route", f"{load.origin} → {load.destination}"),
        ("Commodity", load.commodity),
        ("Truck type", load.truck_type),
        ("Trucks needed", load.trucks_needed),
        ("Rate per truck", f"{load.currency} {load.rate:,.2f}"),
        ("Payment terms", load.payment_terms),
        ("Pickup date", load.pickup_date.isoformat() if load.pickup_date else None),
    ]
    if load.backload_origin:
        rate = f"{load.currency} {load.backload_rate:,.2f}" if load.backload_rate is not None else "-"
        rows.append(("Backload", f"{load.backload_origin} → {load.backload_destination}, {load.backload_commodity} ({rate})"))
    rows += [
        ("Note", load.note),
        ("Company", (company.trading_name or company.legal_name) if company else None),
        ("Posted by", f"{user.full_name} <{user.email}>"),
        ("Posted as", load.posted_as),
        ("Load ID", load.id),
    ]
    tr = "".join(
        '<tr>'
        f'<td style="padding:6px 12px;border-bottom:1px solid #eee;color:#666;font-weight:600;white-space:nowrap">{_esc(k)}</td>'
        f'<td style="padding:6px 12px;border-bottom:1px solid #eee">{_esc(v)}</td>'
        "</tr>"
        for k, v in rows
    )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">'
        f'<h2 style="margin:0 0 4px">New load #{load.id}</h2>'
        '<p style="margin:0 0 16px;color:#666">A new load was posted on CargoFlow Africa.</p>'
        f'<table style="border-collapse:collapse;background:#fafafa;border:1px solid #eee">{tr}</table>'
        '<p style="margin:16px 0 0;color:#999;font-size:12px">Log in to the platform to review it and apply your margins.</p>'
        "</div>"
    )


def _notify_directors(load: Load, company: Company | None, user: User, mailer: BrevoMailer) -> None:
    recipients = [e.strip() for e in settings.LOAD_NOTIFICATION_EMAILS.split(",") if e.strip()]
    if not recipients:
        return
    subject = f"New load #{load.id}: {load.origin} → {load.destination}"
    content = _load_email_html(load, company, user)
    for email in recipients:
        mailer.send_background(to_email=email, subject=subject, html_content=content)


def create_load(db: Session, body: LoadCreate, user: User, mailer: BrevoMailer) -> Load:
    if _is_staff(user):
        company_id = body.company_id
        company = db.get(Company, company_id) if company_id is not None else None
        if company_id is not None and not company:
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
    try:
        _notify_directors(load, company, user, mailer)
    except Exception:
        logger.exception("Failed to queue director notification for load #%s", load.id)
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
