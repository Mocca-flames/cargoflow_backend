from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.features.overview import service
from app.features.overview.schemas import Overview

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=Overview)
def get_overview(
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "director")),
):
    return service.get_overview(db)
