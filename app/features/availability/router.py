from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_active_user
from app.features.availability import service
from app.features.availability.schemas import AvailabilityCreate, AvailabilityOut
from app.features.users.model import User

router = APIRouter(prefix="/availability", tags=["availability"])


@router.post("", response_model=AvailabilityOut, status_code=201)
def post_availability(
    body: AvailabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.post_availability(db, body, user)


@router.get("", response_model=list[AvailabilityOut])
def list_board(
    status: str | None = Query(None, pattern="^(available|needs_backload)$"),
    location: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_active_user),
):
    return service.list_board(db, status, location, limit, offset)


@router.post("/{availability_id}/withdraw", response_model=AvailabilityOut)
def withdraw(
    availability_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.withdraw(db, availability_id, user)
