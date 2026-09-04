from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from config import settings
from database import get_db
from deps import require_admin
from models import AuditLog, Demand, Invoice, User
from schemas import (
    AdminDemandOut,
    AdminInvoiceCreate,
    AdminInvoiceUpdate,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AuditOut,
    DemandDecision,
    InvoiceOut,
)
from security import hash_password
from services import create_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])

DbDep = Annotated[Session, Depends(get_db)]


def _admin_demand_out(demand: Demand) -> AdminDemandOut:
    invoice: Invoice = demand.invoice
    requester: User = demand.requester
    return AdminDemandOut(
        demand_id=demand.demand_id,
        invoice_id=demand.invoice_id,
        invoice_no=invoice.invoice_no,
        supplier=invoice.supplier,
        net_a_payer=invoice.net_a_payer,
        status=demand.status,
        submitted_at=demand.submitted_at,
        user_id=demand.user_id,
        user_name=requester.full_name,
        user_email=requester.email,
    )


@router.get("/demands", response_model=list[AdminDemandOut])
def admin_list_demands(
    db: DbDep,
    admin: User = Depends(require_admin),
    status_filter: str | None = Query(default=None, alias="status"),
):
    """Review queue across all users (admin only), optionally filtered by status."""
    valid = settings.DEMAND_STATUSES | {"all"}
    if status_filter is not None and status_filter not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of: {', '.join(sorted(valid))}",
        )

    stmt = (
        select(Demand)
        .options(selectinload(Demand.invoice), selectinload(Demand.requester))
        .order_by(Demand.submitted_at.desc())
    )
    if status_filter and status_filter in settings.DEMAND_STATUSES:
        stmt = stmt.where(Demand.status == status_filter)

    return [_admin_demand_out(d) for d in db.scalars(stmt).all()]


@router.patch("/demands/{demand_id}", response_model=AdminDemandOut)
def admin_review_demand(
    demand_id: int,
    decision: DemandDecision,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Approve or reject a demand, reflect it on the invoice, and audit it."""
    demand = db.scalar(
        select(Demand)
        .options(selectinload(Demand.invoice), selectinload(Demand.requester))
        .where(Demand.demand_id == demand_id)
    )
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    if demand.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Demand already reviewed (status={demand.status})",
        )

    old_status = demand.status
    demand.status = decision.status
    demand.reviewed_by_admin_id = admin.user_id
    demand.reviewed_at = datetime.now(timezone.utc)
    demand.invoice.status = "approved" if decision.status == "approved" else "rejected"

    create_audit_log(
        db,
        demand=demand,
        actor_id=admin.user_id,
        action="APPROVED_DEMAND" if decision.status == "approved" else "REJECTED_DEMAND",
        field_changed="status",
        old_value=old_status,
        new_value=decision.status,
    )

    db.commit()
    db.refresh(demand)
    return _admin_demand_out(demand)


@router.get("/audit", response_model=list[AuditOut])
def admin_audit_logs(db: DbDep, admin: User = Depends(require_admin)):
    """Full audit trail of admin decisions (admin only), newest first."""
    logs = db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc())).all()
    return logs


@router.get("/users", response_model=list[AdminUserOut])
def admin_list_users(db: DbDep, admin: User = Depends(require_admin)):
    """List all non-admin users for admin management.
 
    Administrator accounts are intentionally excluded from the user manager
    so they cannot be acted upon from this view.
    """
    users = db.scalars(
        select(User).where(User.role == "user").order_by(User.created_at.desc())
    ).all()
    print(users)
    return users


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: AdminUserCreate,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Create a user account from the admin panel."""
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        account_status=payload.account_status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Update a user's basic profile fields from the admin panel."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator accounts cannot be modified",
        )
    if user_id == admin.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot edit your own account here")

    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"] is not None:
        user.full_name = data["full_name"].strip()
    if "email" in data and data["email"] is not None:
        email = str(data["email"]).lower()
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None and existing.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        user.email = email
    if "role" in data and data["role"] is not None:
        user.role = data["role"]
    if "account_status" in data and data["account_status"] is not None:
        user.account_status = data["account_status"]
    if "password" in data and data["password"] is not None:
        user.password_hash = hash_password(data["password"])

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Delete a user from the admin panel."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator accounts cannot be deleted",
        )
    if user_id == admin.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")

    db.delete(user)
    db.commit()
    return None


@router.get("/invoices", response_model=list[InvoiceOut])
def admin_list_invoices(db: DbDep, admin: User = Depends(require_admin)):
    """List all invoices for admin management."""
    invoices = db.scalars(
        select(Invoice)
        .options(selectinload(Invoice.demand), selectinload(Invoice.owner))
        .order_by(Invoice.uploaded_at.desc())
    ).all()
    serialised: list[InvoiceOut] = []
    for invoice in invoices:
        item = InvoiceOut.model_validate(invoice)
        item.demand_id = invoice.demand.demand_id if invoice.demand is not None else None
        item.demand_status = invoice.demand.status if invoice.demand is not None else None
        item.user_name = invoice.owner.full_name if invoice.owner is not None else None
        item.user_email = invoice.owner.email if invoice.owner is not None else None
        serialised.append(item)
    return serialised


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def admin_create_invoice(
    payload: AdminInvoiceCreate,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Create a new invoice record from the admin panel."""
    owner = db.get(User, payload.user_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    invoice = Invoice(
        user_id=payload.user_id,
        file_path=payload.file_path,
        supplier=payload.supplier,
        address=payload.address,
        invoice_no=payload.invoice_no,
        invoice_date=payload.invoice_date,
        amount_excl_tax=payload.amount_excl_tax,
        currency=payload.currency,
        kwh_consumed=payload.kwh_consumed,
        status=payload.status,
        net_a_payer=payload.net_a_payer,
        consumption_jour=payload.consumption_jour,
        consumption_pointe=payload.consumption_pointe,
        consumption_soiree=payload.consumption_soiree,
        consumption_nuit=payload.consumption_nuit,
        pu_jour=payload.pu_jour,
        pu_pointe=payload.pu_pointe,
        pu_soiree=payload.pu_soiree,
        pu_nuit=payload.pu_nuit,
        montant_jour=payload.montant_jour,
        montant_pointe=payload.montant_pointe,
        montant_soiree=payload.montant_soiree,
        montant_nuit=payload.montant_nuit,
        sous_total=payload.sous_total,
        total_1=payload.total_1,
        total_2=payload.total_2,
        total_3=payload.total_3,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    item = InvoiceOut.model_validate(invoice)
    item.demand_id = invoice.demand.demand_id if invoice.demand is not None else None
    item.demand_status = invoice.demand.status if invoice.demand is not None else None
    item.user_name = invoice.owner.full_name if invoice.owner is not None else None
    item.user_email = invoice.owner.email if invoice.owner is not None else None
    return item


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
def admin_update_invoice(
    invoice_id: int,
    payload: AdminInvoiceUpdate,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Update an invoice record from the admin panel."""
    invoice = db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.demand), selectinload(Invoice.owner))
        .where(Invoice.invoice_id == invoice_id)
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(invoice, key, value)

    db.commit()
    db.refresh(invoice)
    item = InvoiceOut.model_validate(invoice)
    item.demand_id = invoice.demand.demand_id if invoice.demand is not None else None
    item.demand_status = invoice.demand.status if invoice.demand is not None else None
    item.user_name = invoice.owner.full_name if invoice.owner is not None else None
    item.user_email = invoice.owner.email if invoice.owner is not None else None
    return item


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_invoice(
    invoice_id: int,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Delete an invoice from the admin panel."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    db.delete(invoice)
    db.commit()
    return None
