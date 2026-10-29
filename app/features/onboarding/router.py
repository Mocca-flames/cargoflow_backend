from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.features.users.model import User
from app.core.email import BrevoMailer, get_mailer
from app.features.auth.schemas import MessageOut
from app.features.onboarding import service
from app.features.onboarding.schemas import OnboardingOut, OnboardingStartIn, OnboardingSubmitIn, StaffOnboardingIn

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/start", response_model=MessageOut)
def start(
    body: OnboardingStartIn,
    db: Session = Depends(get_db),
    mailer: BrevoMailer = Depends(get_mailer),
):
    service.start(db, body.email, mailer)
    return MessageOut(message="Verification code sent to your email")


@router.post("/submit", response_model=OnboardingOut, status_code=201)
def submit(body: OnboardingSubmitIn, db: Session = Depends(get_db)):
    return service.submit(db, body)


@router.post("/staff-submit", response_model=OnboardingOut, status_code=201)
def staff_submit(
    body: StaffOnboardingIn,
    db: Session = Depends(get_db),
    creator: User = Depends(require_role("admin", "director")),
    mailer: BrevoMailer = Depends(get_mailer),
):
    return service.staff_submit(db, body, creator, mailer)
