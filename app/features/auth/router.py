from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.features.auth.schemas import ForgotPasswordIn, ResetPasswordIn

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.email import BrevoMailer, get_mailer
from app.features.auth import service
from app.features.auth.schemas import MeOut, LoginIn, MessageOut, TokenOut, VerifyOtpIn, LoginOut, RefreshIn, ChangePasswordIn
from app.features.users.model import User

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/login', response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db), mailer: BrevoMailer = Depends(get_mailer)):
    tokens = service.login(db, body.email, body.password, mailer, body.device_token)
    if tokens:
        return LoginOut(otp_required=False, tokens=tokens)
    return LoginOut(otp_required=True, message='Verification code sent to your email')


@router.get('/me', response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post('/verify-otp', response_model=TokenOut)
def verify_login_otp(body: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    return service.verify_login_otp(
        db, body.email, body.code, body.remember_device, request.headers.get("user-agent")
    )


@router.post('/refresh', response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    return service.refresh(db, body.refresh_token)


@router.post('/change-password', response_model=TokenOut)
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.change_password(db, user, body.current_password, body.new_password)


@router.post('/forgot-password', response_model=MessageOut)
def forgot_password(
    body: ForgotPasswordIn,
    db: Session = Depends(get_db),
    mailer: BrevoMailer = Depends(get_mailer),
):
    service.forgot_password(db, body.email, mailer)
    return MessageOut(message='If that email exists, a code was sent')

@router.post('/reset-password', response_model=MessageOut)
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    service.reset_password(db, body.email, body.code, body.new_password)
    return MessageOut(message='Password updated. Please log in.')