from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_active_user
from app.features.loads import service
from app.features.loads.schemas import LoadCreate, LoadOut, LoadUpdate, PublicLoadOut
from app.features.users.model import User

router = APIRouter(prefix="/loads", tags=["loads"])


@router.post("", response_model=LoadOut, status_code=201)
def create_load(
    body: LoadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.create_load(db, body, user)


@router.get("", response_model=list[LoadOut])
def list_loads(
    status: str | None = Query(None, pattern="^(open|assigned|closed)$"),
    origin: str | None = None,
    destination: str | None = None,
    truck_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_active_user),
):
    return service.list_loads(db, status, origin, destination, truck_type, limit, offset)


@router.get("/{load_id}", response_model=LoadOut)
def get_load(
    load_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_active_user),
):
    return service.get_load(db, load_id)


@router.patch("/{load_id}", response_model=LoadOut)
def update_load(
    load_id: int,
    body: LoadUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.update_load(db, load_id, body, user)


# Public board: no login, open loads only, no contact or company details.
public_router = APIRouter(prefix="/public/loads", tags=["public-loads"])


@public_router.get("", response_model=list[PublicLoadOut])
def public_list_loads(
    origin: str | None = None,
    destination: str | None = None,
    truck_type: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return service.list_loads(db, "open", origin, destination, truck_type, limit, offset)


@public_router.get("/{load_id}", response_model=PublicLoadOut)
def public_get_load(load_id: int, db: Session = Depends(get_db)):
    return service.get_open_load(db, load_id)
