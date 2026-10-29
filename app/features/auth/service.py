from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import jwt

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import BrevoMailer
from app.core.security import create_token, hash_password, verify_password, decode_token
from app.features.auth.models import TrustedDevice
from app.features.auth.schemas import TokenOut
from app.features.otp.service import issue_otp, send_otp_email, verify_otp
from app.features.users.model import User

LOCK_AFTER_FAILURES = 5
LOCK_MINUTES = 15
GENERIC_LOGIN_ERROR = "Wrong email or password"

# Hashed once at import. Verifying against it for unknown emails keeps response
# time similar to a real user, so emails can't be probed by timing.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def login(db: Session, email: str, password: str, mailer: BrevoMailer,
          device_token: str | None = None) -> TokenOut | None:
    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.email == email.lower().strip()))

    if not user:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(401, GENERIC_LOGIN_ERROR)

    # Locked accounts get the same error, so an attacker can't tell which accounts exist
    if user.locked_until and user.locked_until > now:
        raise HTTPException(401, GENERIC_LOGIN_ERROR)

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= LOCK_AFTER_FAILURES:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_login_count = 0
        db.commit()
        raise HTTPException(401, GENERIC_LOGIN_ERROR)

    if not user.is_active:
        raise HTTPException(401, GENERIC_LOGIN_ERROR)

    user.failed_login_count = 0
    user.locked_until = None

    if device_token:
        device = db.scalar(
            select(TrustedDevice).where(
                TrustedDevice.token_hash == _hash_device_token(device_token),
                TrustedDevice.user_id == user.id,
                TrustedDevice.expires_at > now,
            )
        )
        if device:
            device.last_used_at = now
            user.last_login_at = now
            db.commit()
            return TokenOut(
                access_token=create_token(user.id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES, version=user.token_version),
                refresh_token=create_token(user.id, "refresh", settings.REFRESH_TOKEN_EXPIRE_MINUTES, version=user.token_version),
            )

    db.commit()

    if getattr(settings, "SKIP_OTP", False):
        user.last_login_at = now
        db.commit()
        return TokenOut(
            access_token=create_token(user.id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES, version=user.token_version),
            refresh_token=create_token(user.id, "refresh", settings.REFRESH_TOKEN_EXPIRE_MINUTES, version=user.token_version),
        )

    code = issue_otp(db, user.email, "login", user.id)
    send_otp_email(mailer, user.email, code, "login")
    return None


DEVICE_TRUST_DAYS = 30
GENERIC_OTP_ERROR = "Invalid or expired code"


def _hash_device_token(token: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_login_otp(
    db: Session, email: str, code: str, remember_device: bool, user_agent: str | None
) -> TokenOut:
    email = email.lower().strip()
    now = datetime.now(timezone.utc)

    if not verify_otp(db, email, "login", code):
        raise HTTPException(401, GENERIC_OTP_ERROR)

    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or (user.locked_until and user.locked_until > now):
        raise HTTPException(401, GENERIC_OTP_ERROR)

    user.last_login_at = now

    device_token = None
    if remember_device:
        device_token = secrets.token_urlsafe(32)
        db.add(TrustedDevice(
            user_id=user.id,
            token_hash=_hash_device_token(device_token),
            user_agent=user_agent[:255] if user_agent else None,
            expires_at=now + timedelta(days=DEVICE_TRUST_DAYS),
            last_used_at=now,
        ))

    db.commit()

    return TokenOut(
        access_token=create_token(user.id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES, version=user.token_version),
        refresh_token=create_token(user.id, "refresh", settings.REFRESH_TOKEN_EXPIRE_MINUTES, version=user.token_version),
        device_token=device_token,
    )


def change_password(db: Session, user: User, current_password: str, new_password: str) -> TokenOut:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if verify_password(new_password, user.password_hash):
        raise HTTPException(400, "New password must be different from the current one")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.token_version += 1  # kills every existing access and refresh token
    db.execute(delete(TrustedDevice).where(TrustedDevice.user_id == user.id))
    db.commit()

    # Fresh tokens for the current session so the user isn't logged out
    return TokenOut(
        access_token=create_token(user.id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES, version=user.token_version),
        refresh_token=create_token(user.id, "refresh", settings.REFRESH_TOKEN_EXPIRE_MINUTES, version=user.token_version),
    )


def refresh(db: Session, refresh_token: str) -> TokenOut:
    now = datetime.now(timezone.utc)
    try:
        data = decode_token(refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    if data.get("type") != "refresh":
        raise HTTPException(401, "Invalid token")

    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active or (user.locked_until and user.locked_until > now):
        raise HTTPException(401, "Invalid token")
    if data.get("ver", 0) != user.token_version:
        raise HTTPException(401, "Invalid token")

    return TokenOut(
        access_token=create_token(user.id, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES, version=user.token_version),
        refresh_token=create_token(user.id, "refresh", settings.REFRESH_TOKEN_EXPIRE_MINUTES, version=user.token_version),
    )

def forgot_password(db: Session, email: str, mailer: BrevoMailer) -> None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if not user or not user.is_active:
        return  # same response as success, so emails can't be probed

    try:
        code = issue_otp(db, user.email, "password_reset", user.id)
    except HTTPException:
        return  # cooldown hit: stay silent, don't reveal the account exists

    send_otp_email(mailer, user.email, code, "password_reset")


def reset_password(db: Session, email: str, code: str, new_password: str) -> None:
    email = email.lower().strip()

    if not verify_otp(db, email, "password_reset", code):
        raise HTTPException(400, GENERIC_OTP_ERROR)

    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active:
        raise HTTPException(400, GENERIC_OTP_ERROR)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.token_version += 1  # kills every existing access and refresh token
    user.failed_login_count = 0
    user.locked_until = None  # the user proved control of their email
    db.execute(delete(TrustedDevice).where(TrustedDevice.user_id == user.id))
    db.commit()