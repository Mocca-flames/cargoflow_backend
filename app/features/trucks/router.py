from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_active_user
from app.features.trucks import service
from app.features.trucks.schemas import TruckCreate, TruckDetail, TruckOut, TruckUpdate
from app.features.users.model import User

router = APIRouter(prefix="/trucks", tags=["trucks"])


@router.post("", response_model=TruckOut, status_code=201)
def create_truck(
    body: TruckCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.create_truck(db, body, user)


@router.get("", response_model=list[TruckOut])
def list_trucks(
    company_id: int | None = None,
    active: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.list_trucks(db, user, company_id, active, limit, offset)


@router.patch("/{truck_id}", response_model=TruckOut)
def update_truck(
    truck_id: int,
    body: TruckUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.update_truck(db, truck_id, body, user)


@router.get("/{truck_id}", response_model=TruckDetail)
def get_truck(
    truck_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    return service.get_truck(db, truck_id, user)
