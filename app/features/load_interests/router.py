from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.features.load_interests import service
from app.features.load_interests.schemas import (
    InterestCreate,
    InterestOut,
    InterestReceived,
    InterestUpdate,
)
from app.features.users.model import User

# Public: a visitor says "I have a truck for this load". No login, no OTP.
public_router = APIRouter(prefix="/public/loads", tags=["public-loads"])


@public_router.post("/{load_id}/interest", response_model=InterestReceived, status_code=201)
def submit_interest(load_id: int, body: InterestCreate, db: Session = Depends(get_db)):
    return service.submit_interest(db, load_id, body)


# Admin: the callback list.
router = APIRouter(prefix="/load-interests", tags=["load-interests"])


@router.get("", response_model=list[InterestOut])
def list_interests(
    status: str | None = Query(None, pattern="^(new|contacted|onboarded|dismissed)$"),
    load_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "director")),
):
    return service.list_interests(db, status, load_id, limit, offset)


@router.patch("/{interest_id}", response_model=InterestOut)
def update_interest(
    interest_id: int,
    body: InterestUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin", "director")),
):
    return service.update_interest(db, interest_id, body, admin)
