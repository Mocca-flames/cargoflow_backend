import secrets
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.email import BrevoMailer
from app.features.otp.service import issue_otp, send_otp_email
from app.features.users.model import User
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password
from app.features.companies.models import BrokerProfile, Company, CompanyRole, TransporterProfile
from app.features.onboarding.schemas import CompanyOnboardingBase, OnboardingOut, OnboardingSubmitIn, StaffOnboardingIn
from app.features.otp.service import verify_otp

PURPOSE = "email_verify"


def start(db: Session, email: str, mailer: BrevoMailer) -> None:
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please log in.",
        )
    code = issue_otp(db, email, PURPOSE)
    send_otp_email(mailer, email, code, PURPOSE)


def submit(db: Session, body: OnboardingSubmitIn) -> OnboardingOut:
    owner = body.owner
    c = body.company

    if db.scalar(select(User.id).where(User.email == owner.email)):
        raise HTTPException(409, "An account with this email already exists. Please log in.")
    if db.scalar(select(User.id).where(User.phone == owner.phone)):
        raise HTTPException(409, "An account with this phone number already exists.")
    if db.scalar(select(Company.id).where(
        Company.country_code == c.country_code,
        Company.registration_number == c.registration_number,
    )):
        raise HTTPException(409, "A company with this registration number already exists. Please contact support.")

    if not verify_otp(db, owner.email, PURPOSE, body.code):
        raise HTTPException(400, "Invalid or expired code.")

    try:
        company = _add_company(db, body)

        user = User(
            email=owner.email,
            phone=owner.phone,
            full_name=owner.full_name,
            password_hash=hash_password(body.password),
            company_id=company.id,
        )
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This company, email or phone is already registered.")

    return OnboardingOut(
        company_id=company.id,
        status=company.status,
        roles=list(body.roles),
        owner_user_id=user.id,
        message="Registration received. Your company is pending verification. You can log in now.",
    )


def _add_company(db: Session, body: CompanyOnboardingBase) -> Company:
    c = body.company
    company = Company(
        legal_name=c.legal_name,
        trading_name=c.trading_name,
        registration_number=c.registration_number,
        country_code=c.country_code,
        phone=c.phone,
    )
    db.add(company)
    db.flush()
    for role in body.roles:
        db.add(CompanyRole(company_id=company.id, role=role))
    if body.transporter:
        db.add(TransporterProfile(
            company_id=company.id,
            operating_countries=body.transporter.operating_countries,
        ))
    if body.broker:
        db.add(BrokerProfile(
            company_id=company.id,
            corridors=body.broker.corridors,
            finds_trucks=body.broker.finds_trucks,
        ))
    return company


def staff_submit(db: Session, body: StaffOnboardingIn, creator: User, mailer: BrevoMailer) -> OnboardingOut:
    c = body.company
    owner = body.owner if body.create_owner else None

    if db.scalar(select(Company.id).where(
        Company.country_code == c.country_code,
        Company.registration_number == c.registration_number,
    )):
        raise HTTPException(409, "A company with this registration number already exists.")
    if owner:
        if db.scalar(select(User.id).where(User.email == owner.email)):
            raise HTTPException(409, "An account with this email already exists.")
        if db.scalar(select(User.id).where(User.phone == owner.phone)):
            raise HTTPException(409, "An account with this phone number already exists.")

    user = None
    temp_password = None
    try:
        company = _add_company(db, body)
        if owner:
            temp_password = secrets.token_urlsafe(9)
            user = User(
                email=owner.email,
                phone=owner.phone,
                full_name=owner.full_name,
                password_hash=hash_password(temp_password),
                company_id=company.id,
                must_change_password=True,
                created_by=creator.id,
            )
            db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This company, email or phone is already registered.")

    if user:
        mailer.send_background(
            to_email=user.email,
            to_name=user.full_name,
            subject="Your CargoFlow account",
            html_content=(
                f"<p>Hi {user.full_name},</p>"
                f"<p>Your temporary password is <b>{temp_password}</b>.</p>"
                f"<p>You will be asked to change it when you log in.</p>"
            ),
        )

    return OnboardingOut(
        company_id=company.id,
        status=company.status,
        roles=list(body.roles),
        owner_user_id=user.id if user else None,
        message="Company created and pending verification.",
    )
