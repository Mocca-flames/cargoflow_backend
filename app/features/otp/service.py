from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import secrets

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import BrevoMailer
from app.features.otp.models import OtpCode


def _hash_code(code: str) -> str:
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, code.encode("utf-8"), hashlib.sha256).hexdigest()


def _norm(email: str) -> str:
    return email.lower().strip()


def _latest_active(db: Session, email: str, purpose: str, lock: bool = False):
    stmt = (
        select(OtpCode)
        .where(OtpCode.email == email, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def issue_otp(db: Session, email: str, purpose: str, user_id: int | None = None) -> str:
    email = _norm(email)
    now = datetime.now(timezone.utc)

    latest = _latest_active(db, email, purpose)
    if latest and (now - latest.created_at) < timedelta(seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before requesting another code.")

    db.execute(
        update(OtpCode)
        .where(OtpCode.email == email, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(OtpCode(
        email=email,
        user_id=user_id,
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=now + timedelta(minutes=10),
    ))
    db.commit()
    return code


def verify_otp(db: Session, email: str, purpose: str, code: str) -> bool:
    email = _norm(email)
    now = datetime.now(timezone.utc)

    otp = _latest_active(db, email, purpose, lock=True)
    if not otp or otp.expires_at < now or otp.attempts >= otp.max_attempts:
        db.rollback()
        return False

    if not hmac.compare_digest(_hash_code(code), otp.code_hash):
        otp.attempts += 1
        db.commit()
        return False

    otp.consumed_at = now
    db.commit()
    return True


def send_otp_email(mailer: BrevoMailer, email: str, code: str, purpose: str) -> None:
    subject = f"Your {purpose.replace('_', ' ')} code"
    html_content = f"""
    <html>
      <body>
        <p>Your verification code is: <strong>{code}</strong></p>
        <p>This code expires in 10 minutes.</p>
      </body>
    </html>
    """
    mailer.send_background(
        to_email=email,
        subject=subject,
        html_content=html_content,
    )
