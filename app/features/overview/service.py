from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.companies.models import Company
from app.features.loads.models import Load
from app.features.load_interests.models import LoadInterest
from app.features.overview.schemas import Overview, TrendPoint

WINDOW = 14


def get_overview(db: Session) -> Overview:
    today = date.today()
    start = today - timedelta(days=WINDOW - 1)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # Current-state counters (cheap COUNT(*)s, no row dumps)
    open_loads = db.scalar(
        select(func.count()).select_from(Load).where(Load.status == "open")
    )
    unverified = db.scalar(
        select(func.count()).select_from(Company).where(Company.status == "unverified")
    )
    new_interests = db.scalar(
        select(func.count()).select_from(LoadInterest).where(LoadInterest.status == "new")
    )

    # 7-day growth metrics
    onboarded_7d = db.scalar(
        select(func.count()).select_from(Company).where(
            Company.status == "verified",
            Company.verified_at.is_not(None),
            Company.verified_at >= week_ago,
        )
    )
    converted_7d = db.scalar(
        select(func.count()).select_from(LoadInterest).where(
            LoadInterest.status == "onboarded",
            LoadInterest.handled_at.is_not(None),
            LoadInterest.handled_at >= week_ago,
        )
    )

    # 14-day daily buckets, zero-filled in Python (fewer queries than group-by day)
    interest_days = dict(
        db.execute(
            select(func.date(LoadInterest.created_at), func.count())
            .where(LoadInterest.created_at >= start)
            .group_by(func.date(LoadInterest.created_at))
        ).all()
    )
    company_days = dict(
        db.execute(
            select(func.date(Company.created_at), func.count())
            .where(Company.created_at >= start)
            .group_by(func.date(Company.created_at))
        ).all()
    )

    trend = [
        TrendPoint(
            date=start + timedelta(days=off),
            new_interests=interest_days.get(start + timedelta(days=off), 0),
            onboarded_companies=company_days.get(start + timedelta(days=off), 0),
        )
        for off in range(WINDOW)
    ]

    return Overview(
        open_loads=open_loads or 0,
        unverified_companies=unverified or 0,
        new_interests=new_interests or 0,
        onboarded_companies_7d=onboarded_7d or 0,
        converted_leads_7d=converted_7d or 0,
        trend=trend,
        generated_at=datetime.now(timezone.utc),
    )
