from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from deps import get_current_user
from models import Demand, Invoice, User
from schemas import (
    InvoiceListResponse,
    InvoiceOut,
    InvoiceUploadResponse,
    InvoiceValuesUpdate,
)
from services import create_audit_log, save_upload_file

router = APIRouter(prefix="/invoices", tags=["invoices"])

DbDep = Annotated[Session, Depends(get_db)]


def _invoice_out(invoice: Invoice) -> InvoiceOut:
    """Serialize an ORM invoice into the wire schema, merging its demand info."""
    data = InvoiceOut.model_validate(invoice)
    demand: Demand | None = getattr(invoice, "demand", None)
    if demand is not None:
        data.demand_id = demand.demand_id
        data.demand_status = demand.status
    return data


def _own_invoice_or_404(db: Session, invoice_id: int, user: User) -> Invoice:
    invoice = db.scalar(
        select(Invoice).options(selectinload(Invoice.demand)).where(Invoice.invoice_id == invoice_id)
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.user_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your invoice")
    return invoice


@router.post("/upload", response_model=InvoiceUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_invoice(
    file: UploadFile,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    """Save a facture PDF/image and create the invoice row (status='uploaded')."""
    file_path = save_upload_file(file)
    invoice = Invoice(user_id=current_user.user_id, file_path=file_path, uploaded_at=datetime.now())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return InvoiceUploadResponse(invoice=_invoice_out(invoice))


@router.get("/mine", response_model=InvoiceListResponse)
def list_my_invoices(db: DbDep, current_user: User = Depends(get_current_user)):
    """All invoices belonging to the authenticated user, newest first."""
    invoices = db.scalars(
        select(Invoice)
        .options(selectinload(Invoice.demand))
        .where(Invoice.user_id == current_user.user_id)
        .order_by(Invoice.uploaded_at.desc())
    ).all()
    return InvoiceListResponse(invoices=[_invoice_out(i) for i in invoices], total=len(invoices))


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    """Fetch a single invoice (owner or admin only)."""
    invoice = _own_invoice_or_404(db, invoice_id, current_user)
    return _invoice_out(invoice)


@router.put("/{invoice_id}/values", response_model=InvoiceOut)
def update_invoice_values(
    invoice_id: int,
    payload: InvoiceValuesUpdate,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    """Persist user-validated extraction values.
    
    If a demand already exists for this invoice (whether pending, validated or rejected),
    modifying the values resets the demand status back to 'pending' for admin re-validation.
    """
    invoice = _own_invoice_or_404(db, invoice_id, current_user)

    invoice.supplier = payload.supplier
    invoice.invoice_no = payload.invoice_no
    invoice.invoice_date = payload.invoice_date
    invoice.amount_excl_tax = payload.amount_excl_tax
    invoice.tva = payload.tva
    invoice.amount_incl_tax = payload.amount_incl_tax
    invoice.currency = payload.currency
    invoice.kwh_consumed = payload.kwh_consumed
    invoice.due_date = payload.due_date

    demand: Demand | None = invoice.demand
    if demand is not None:
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
    else:
        invoice.status = "validated_by_user"

    db.commit()
    db.refresh(invoice)
    return _invoice_out(invoice)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_invoice(
    invoice_id: int,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    """Delete an invoice belonging to the current user (and cascade delete demand)."""
    invoice = _own_invoice_or_404(db, invoice_id, current_user)
    db.delete(invoice)
    db.commit()
    return None

