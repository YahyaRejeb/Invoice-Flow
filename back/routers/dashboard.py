from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user, require_admin
from models import Demand, Invoice, User
from schemas import DashboardStats

router = APIRouter(tags=["dashboard"])

DbDep = Annotated[Session, Depends(get_db)]


def _stats_for(db: Session, user_id: int) -> DashboardStats:
    def _count(stmt):
        return db.scalar(stmt) or 0

    invoices = _count(
        select(func.count(Invoice.invoice_id)).where(Invoice.user_id == user_id)
    )
    pending = _count(
        select(func.count(Demand.demand_id)).where(
            Demand.user_id == user_id, Demand.status == "pending"
        )
    )
    approved = _count(
        select(func.count(Demand.demand_id)).where(
            Demand.user_id == user_id, Demand.status == "approved"
        )
    )
    total_kwh = _count(
        select(func.coalesce(func.sum(Invoice.kwh_consumed), 0)).where(
            Invoice.user_id == user_id
        )
    )

    return DashboardStats(
        user_id=user_id,
        total_invoices=invoices,
        pending_demands=pending,
        validated_demands=approved,
        total_kwh=int(total_kwh),
    )


@router.get("/dashboard/me", response_model=DashboardStats)
def my_dashboard_stats(db: DbDep, current_user: User = Depends(get_current_user)):
    """Aggregate overview figures for the authenticated user."""
    return _stats_for(db, current_user.user_id)


@router.get("/admin/dashboard/{user_id}", response_model=DashboardStats)
def admin_user_dashboard_stats(
    user_id: int,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Aggregate overview figures for a specific user (admin only)."""
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _stats_for(db, user_id)
