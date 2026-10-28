from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.core.email import BrevoMailer, get_mailer
from app.features.users import service
from app.features.users.model import User
from app.features.users.schemas import UserCreate, UserOut

router = APIRouter(prefix='/users', tags=['users'])


@router.post('', response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    creator: User = Depends(require_role('admin', 'director')),
    mailer: BrevoMailer = Depends(get_mailer),
):
    user, temp_password = service.create_user(db, body, creator)
    mailer.send_background(
        to_email=user.email,
        to_name=user.full_name,
        subject='Your CargoFlow account',
        html_content=(
            f'<p>Hi {user.full_name},</p>'
            f'<p>Your temporary password is <b>{temp_password}</b>.</p>'
            f'<p>You will be asked to change it when you log in.</p>'
        ),
    )
    return user