from datetime import date as date_type, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from deps import get_current_user
from models import Demand, Invoice, User
from schemas import (
    ConsommationDetaillee,
    InvoiceListResponse,
    InvoiceOut,
    InvoiceUploadResponse,
    InvoiceValuesUpdate,
    MontantDetaille,
    OcrResultOut,
    PrixUnitaire,
)
from services import create_audit_log, save_upload_file

import logging

logger = logging.getLogger("steg.invoices")

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
    """Save a facture PDF/image, run OCR extraction, and create the invoice row."""
    file_path = save_upload_file(file)
    invoice = Invoice(user_id=current_user.user_id, file_path=file_path, uploaded_at=datetime.now())

    # --- Run OCR on the saved file ---
    ocr_result = None
    ocr_data_out = None
    try:
        from ocr_service import run_ocr
        from config import UPLOADS_DIR

        # file_path is relative to UPLOADS_DIR.parent (e.g. "uploads/abc123.pdf")
        abs_file_path = str(UPLOADS_DIR.parent / file_path)
        ocr_result = run_ocr(abs_file_path)

        # Auto-populate the invoice row with mapped OCR values
        mapped = ocr_result.get("mapped", {})
        if mapped.get("address"):
            invoice.address = mapped["address"]
        if mapped.get("invoice_no"):
            invoice.invoice_no = mapped["invoice_no"]
        if mapped.get("invoice_date"):
            try:
                invoice.invoice_date = date_type.fromisoformat(mapped["invoice_date"])
            except (ValueError, TypeError):
                pass
        if mapped.get("amount_excl_tax") is not None:
            invoice.amount_excl_tax = mapped["amount_excl_tax"]
        if mapped.get("tva") is not None:
            invoice.tva = mapped["tva"]
        if mapped.get("amount_incl_tax") is not None:
            invoice.amount_incl_tax = mapped["amount_incl_tax"]
        if mapped.get("currency"):
            invoice.currency = mapped["currency"]

        # --- New tariff columns (STEG OCR Expansion) ---
        # Consumption: 0 is a valid value (missing tariff period), not a skip condition
        for col in ("consumption_jour", "consumption_pointe",
                    "consumption_soiree", "consumption_nuit"):
            if mapped.get(col) is not None:
                setattr(invoice, col, mapped[col])
        # PU: same rule
        for col in ("pu_jour", "pu_pointe", "pu_soiree", "pu_nuit"):
            if mapped.get(col) is not None:
                setattr(invoice, col, mapped[col])
        # Detailed Montant
        for col in ("montant_jour", "montant_pointe",
                    "montant_soiree", "montant_nuit"):
            if mapped.get(col) is not None:
                setattr(invoice, col, mapped[col])
        # Summary rows: only store if extraction succeeded (not None)
        for col in ("sous_total", "total_1", "total_2",
                    "total_3", "net_a_payer"):
            if mapped.get(col) is not None:
                setattr(invoice, col, mapped[col])

        # Build the OCR data for the API response
        raw = ocr_result.get("ocr_raw", {})
        ocr_data_out = OcrResultOut(
            consomateur=raw.get("consomateur"),
            address=raw.get("address"),
            facture=raw.get("facture"),
            date=raw.get("date"),
            montant_ht=raw.get("montant_ht"),
            total_3_taxes=raw.get("total_3_taxes"),
            montant_ttc=raw.get("montant_ttc"),
            devise=raw.get("devise", "TND"),
            ocr_status=ocr_result.get("ocr_status"),
            confidence=ocr_result.get("confidence"),
            # --- New structured tariff fields ---
            consommation_detaillee=ConsommationDetaillee(
                **raw["consommation_detaillee"]
            ) if raw.get("consommation_detaillee") else None,
            prix_unitaire=PrixUnitaire(
                **raw["prix_unitaire"]
            ) if raw.get("prix_unitaire") else None,
            montant_detaille=MontantDetaille(
                **raw["montant_detaille"]
            ) if raw.get("montant_detaille") else None,
            sous_total=raw.get("sous_total"),
            total_1=raw.get("total_1"),
            total_2=raw.get("total_2"),
            total_3=raw.get("total_3"),
            net_a_payer=raw.get("net_a_payer"),
            net_a_payer_table_reading=raw.get("net_a_payer_table_reading"),
            net_a_payer_coupon_reading=raw.get("net_a_payer_coupon_reading"),
            net_a_payer_cross_check_match=raw.get("net_a_payer_cross_check_match"),
        )
        logger.info("OCR extraction succeeded for %s", file_path)
    except Exception:
        logger.exception("OCR extraction failed for %s — invoice saved without OCR data", file_path)

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return InvoiceUploadResponse(
        invoice=_invoice_out(invoice),
        ocr_data=ocr_data_out,
        message="Upload successful. OCR extraction complete." if ocr_data_out else "Upload successful. OCR extraction failed — please fill in values manually.",
    )


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
    invoice.address = payload.address
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
        demand = Demand(
            invoice_id=invoice.invoice_id,
            user_id=current_user.user_id,
            status="pending",
            submitted_at=datetime.now(),
        )
        invoice.status = "pending"
        db.add(demand)

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
