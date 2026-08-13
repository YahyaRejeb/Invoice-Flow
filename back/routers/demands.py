from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from deps import get_current_user
from models import Demand, Invoice, User
from schemas import DemandCreate, DemandOut, MyDemandOut
from services import create_audit_log

router = APIRouter(prefix="/demands", tags=["demands"])

DbDep = Annotated[Session, Depends(get_db)]


def _my_demand_out(demand: Demand) -> MyDemandOut:
    invoice: Invoice = demand.invoice
    return MyDemandOut(
        demand_id=demand.demand_id,
        invoice_id=demand.invoice_id,
        invoice_no=invoice.invoice_no,
        supplier=invoice.supplier,
        amount_incl_tax=invoice.amount_incl_tax,
        status=demand.status,
        submitted_at=demand.submitted_at,
    )


@router.post("", response_model=DemandOut, status_code=status.HTTP_201_CREATED)
def submit_demand(
    payload: DemandCreate,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    """Submit or re-submit a formal demand for a user-validated invoice."""
    invoice = db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.demand))
        .where(Invoice.invoice_id == payload.invoice_id)
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your invoice")

    # If a demand already exists, update/re-submit it to pending state for admin review
    if invoice.demand is not None:
        demand = invoice.demand
        old_status = demand.status
        demand.status = "pending"
        demand.submitted_at = datetime.now()
        demand.reviewed_by_admin_id = None
        demand.reviewed_at = None
        invoice.status = "pending"

        create_audit_log(
            db,
            demand=demand,
            actor_id=current_user.user_id,
            action="USER_MODIFIED_DEMAND",
            field_changed="status",
            old_value=old_status,
            new_value="pending",
        )
        db.commit()
        db.refresh(demand)
        return demand

    if invoice.status != "validated_by_user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice must be user-validated before a demand can be submitted",
        )

    demand = Demand(
        invoice_id=invoice.invoice_id,
        user_id=current_user.user_id,
        status="pending",
        submitted_at=datetime.now(),
    )
    invoice.status = "pending"
    db.add(demand)
    db.commit()
    db.refresh(demand)
    return demand


@router.get("/mine", response_model=list[MyDemandOut])
def list_my_demands(db: DbDep, current_user: User = Depends(get_current_user)):
    """All demands submitted by the authenticated user, newest first."""
    demands = db.scalars(
        select(Demand)
        .options(selectinload(Demand.invoice))
        .where(Demand.user_id == current_user.user_id)
        .order_by(Demand.submitted_at.desc())
    ).all()
    return [_my_demand_out(d) for d in demands]


@router.delete("/{demand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_demand(
    demand_id: int,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    """Delete a demand belonging to the current user."""
    demand = db.scalar(
        select(Demand)
        .options(selectinload(Demand.invoice))
        .where(Demand.demand_id == demand_id, Demand.user_id == current_user.user_id)
    )
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")

    if demand.invoice:
        demand.invoice.status = "validated_by_user"

    db.delete(demand)
    db.commit()
    return None

