import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.features.users.model import User
from app.features.users.schemas import STAFF_ROLES, UserCreate


def create_user(db: Session, body: UserCreate, creator: User) -> tuple[User, str]:
    email = body.email.lower().strip()

    if body.staff_role in {'admin', 'director'} and creator.staff_role != 'director':
        raise HTTPException(403, 'Only a director can create admins or directors')

    if body.staff_role in STAFF_ROLES and email.split('@')[1] not in settings.STAFF_EMAIL_DOMAINS:
        raise HTTPException(400, 'Staff must use a company email')

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'Email already exists')

    temp_password = secrets.token_urlsafe(9)
    user = User(
        email=email,
        phone=body.phone,
        full_name=body.full_name,
        staff_role=body.staff_role,
        company_id=body.company_id,
        password_hash=hash_password(temp_password),
        must_change_password=True,
        created_by=creator.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, temp_password