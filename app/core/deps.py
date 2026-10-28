from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.features.users.model import User


bearer = HTTPBearer()


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    token = creds.credentials
    try:
        data = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(401, 'Invalid token')
    if data.get('type') != 'access':
        raise HTTPException(401, 'Invalid token')
    user = db.get(User, int(data['sub']))
    if not user or not getattr(user, 'is_active', False):
        raise HTTPException(401, 'Invalid token')
    if data.get("ver", 0) != user.token_version:
        raise HTTPException(401, 'Invalid token')
    return user


def get_active_user(user: User = Depends(get_current_user)) -> User:
    if user.must_change_password:
        raise HTTPException(403, 'Password change required')
    return user


def require_role(*roles: str):
    def check(user: User = Depends(get_active_user)):
        if getattr(user, 'staff_role') not in roles:
            raise HTTPException(403, 'Not allowed')
        return user
    return check

