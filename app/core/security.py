from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash  # type: ignore
from app.core.config import settings

hasher = PasswordHash.recommended()   # argon2


def hash_password(p: str) -> str:
    return hasher.hash(p)


def verify_password(p: str, h: str) -> bool:
    return hasher.verify(p, h)


def create_token(user_id: int, kind: str, minutes: int, version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "type": kind,   # "access" or "refresh"
        "ver": version,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])