"""Pydantic schemas (request/response models) for the STEG backend.

All Pydantic models live here so every schema is importable with a single
``from schemas import ...`` statement, matching the flat NewsHub layout.
"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    role: str
    account_status: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateMeRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)


class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    role: str = Field(pattern="^(user|admin)$")
    account_status: str = Field(default="pending", pattern="^(pending|active|inactive)$")
    password: str = Field(min_length=6, max_length=128)


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    account_status: str | None = Field(default=None, pattern="^(pending|active|inactive)$")
    password: str | None = Field(default=None, min_length=6, max_length=128)


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    role: str
    account_status: str
    created_at: datetime


class AdminInvoiceCreate(BaseModel):
    user_id: int = Field(gt=0)
    file_path: str = Field(min_length=1, max_length=500)
    supplier: str = Field(default="STEG", max_length=100)
    address: str | None = Field(default=None, max_length=255)
    invoice_no: str | None = Field(default=None, max_length=50)
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    net_a_payer: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    currency: str = Field(default="TND", max_length=10)
    kwh_consumed: int | None = Field(default=None, ge=0)
    status: str = Field(default="uploaded", pattern="^(uploaded|pending|approved|rejected)$")

    # --- Detailed tariff breakdown (STEG OCR Expansion) — all optional ---
    consumption_jour: int | None = Field(default=None, ge=0)
    consumption_pointe: int | None = Field(default=None, ge=0)
    consumption_soiree: int | None = Field(default=None, ge=0)
    consumption_nuit: int | None = Field(default=None, ge=0)
    pu_jour: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_pointe: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_soiree: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_nuit: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_jour: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_pointe: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_soiree: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_nuit: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    sous_total: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_1: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_2: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_3: Decimal | None = Field(default=None, ge=0, decimal_places=3)


class AdminInvoiceUpdate(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    file_path: str | None = Field(default=None, min_length=1, max_length=500)
    supplier: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    invoice_no: str | None = Field(default=None, max_length=50)
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    net_a_payer: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    currency: str | None = Field(default=None, max_length=10)
    kwh_consumed: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(uploaded|pending|approved|rejected)$")

    # --- Detailed tariff breakdown (STEG OCR Expansion) — all optional ---
    consumption_jour: int | None = Field(default=None, ge=0)
    consumption_pointe: int | None = Field(default=None, ge=0)
    consumption_soiree: int | None = Field(default=None, ge=0)
    consumption_nuit: int | None = Field(default=None, ge=0)
    pu_jour: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_pointe: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_soiree: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_nuit: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_jour: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_pointe: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_soiree: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_nuit: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    sous_total: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_1: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_2: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_3: Decimal | None = Field(default=None, ge=0, decimal_places=3)



# ---------------------------------------------------------------------------
# Invoice — tariff detail nested models (STEG OCR Expansion)
# ---------------------------------------------------------------------------

class ConsommationDetaillee(BaseModel):
    """Consumption (kWh) per tariff period. Missing periods are 0."""
    jour: int = 0
    pointe: int = 0
    soiree: int = 0
    nuit: int = 0


class PrixUnitaire(BaseModel):
    """Unit price (millimes/kWh) per tariff period. Missing periods are 0."""
    jour: int = 0
    pointe: int = 0
    soiree: int = 0
    nuit: int = 0


class MontantDetaille(BaseModel):
    """Detailed monetary amount per tariff period. Missing periods are '0.000'."""
    jour: str = "0.000"
    pointe: str = "0.000"
    soiree: str = "0.000"
    nuit: str = "0.000"


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceValuesUpdate(BaseModel):
    """Validated fields the user confirms after reviewing the OCR output."""

    supplier: str = Field(default="STEG", max_length=100)
    address: str | None = Field(default=None, max_length=255)
    invoice_no: str | None = Field(default=None, max_length=50)
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    currency: str = Field(default="TND", max_length=10)
    kwh_consumed: int | None = Field(default=None, ge=0)

    # --- Detailed tariff breakdown (STEG OCR Expansion) — all optional ---
    consumption_jour: int | None = Field(default=None, ge=0)
    consumption_pointe: int | None = Field(default=None, ge=0)
    consumption_soiree: int | None = Field(default=None, ge=0)
    consumption_nuit: int | None = Field(default=None, ge=0)
    pu_jour: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_pointe: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_soiree: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    pu_nuit: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_jour: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_pointe: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_soiree: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    montant_nuit: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    sous_total: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_1: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_2: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    total_3: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    net_a_payer: Decimal | None = Field(default=None, ge=0, decimal_places=3)



class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: int
    user_id: int
    file_name: str | None = None
    file_path: str | None = None
    supplier: str | None = None
    address: str | None = None
    invoice_no: str | None = None
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = None
    currency: str | None = None
    kwh_consumed: int | None = None
    status: str | None = None
    uploaded_at: datetime | None = None
    demand_id: int | None = None
    demand_status: str | None = None
    user_name: str | None = None
    user_email: str | None = None

    # --- New fields: detailed tariff breakdown (STEG OCR Expansion) ---
    consumption_jour: int | None = None
    consumption_pointe: int | None = None
    consumption_soiree: int | None = None
    consumption_nuit: int | None = None
    pu_jour: Decimal | None = None
    pu_pointe: Decimal | None = None
    pu_soiree: Decimal | None = None
    pu_nuit: Decimal | None = None
    montant_jour: Decimal | None = None
    montant_pointe: Decimal | None = None
    montant_soiree: Decimal | None = None
    montant_nuit: Decimal | None = None
    sous_total: Decimal | None = None
    total_1: Decimal | None = None
    total_2: Decimal | None = None
    total_3: Decimal | None = None
    net_a_payer: Decimal | None = None


class OcrResultOut(BaseModel):
    """Raw OCR extraction results returned alongside the uploaded invoice."""

    # --- Existing fields (preserved for backward compatibility) ---
    consomateur: str | None = None
    address: str | None = None
    facture: str | None = None
    date: str | None = None
    montant_ht: str | None = None
    total_3_taxes: str | None = None
    montant_ttc: str | None = None
    devise: str = "TND"
    ocr_status: str | None = None
    confidence: dict | None = None
    processing_time: float | None = None
    time_taken: str | None = None

    # --- New fields: detailed tariff breakdown (STEG OCR Expansion) ---
    consommation_detaillee: ConsommationDetaillee | None = None
    prix_unitaire: PrixUnitaire | None = None
    montant_detaille: MontantDetaille | None = None
    sous_total: str | None = None
    total_1: str | None = None
    total_2: str | None = None
    total_3: str | None = None
    net_a_payer: str | None = None
    # Cross-check readings (preserved from existing extraction)
    net_a_payer_table_reading: str | None = None
    net_a_payer_coupon_reading: str | None = None
    net_a_payer_cross_check_match: bool | None = None


class InvoiceUploadResponse(BaseModel):
    invoice: InvoiceOut
    ocr_data: OcrResultOut | None = None
    message: str = "Upload successful."


class BatchUploadResult(BaseModel):
    """Result for a single file in a batch upload."""
    filename: str
    success: bool
    invoice: InvoiceOut | None = None
    ocr_data: OcrResultOut | None = None
    message: str
    error: str | None = None


class BatchUploadResponse(BaseModel):
    """Response for batch upload containing results for all files."""
    total: int
    successful: int
    failed: int
    results: list[BatchUploadResult]


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceOut]
    total: int


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------

class DemandCreate(BaseModel):
    invoice_id: int = Field(gt=0)


class DemandOut(BaseModel):
    """Full demand record (used internally / admin)."""

    model_config = ConfigDict(from_attributes=True)

    demand_id: int
    invoice_id: int
    user_id: int
    status: str
    submitted_at: datetime
    reviewed_by_admin_id: int | None = None
    reviewed_at: datetime | None = None


class MyDemandOut(BaseModel):
    """Demand enriched with the invoice key figures, for the user's table."""

    demand_id: int
    invoice_id: int
    invoice_no: str | None = None
    supplier: str | None = None
    net_a_payer: Decimal | None = None
    status: str
    submitted_at: datetime


class AdminDemandOut(MyDemandOut):
    """Demand enriched with requester identity, for the admin review queue."""

    user_id: int
    user_name: str | None = None
    user_email: str | None = None


class DemandDecision(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: int
    demand_id: int
    action: str
    actor_id: int
    field_changed: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    timestamp: datetime


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    """Aggregate figures for the overview dashboard, scoped to a user."""

    user_id: int
    total_invoices: int
    pending_demands: int
    validated_demands: int
    total_kwh: int | None = None


__all__ = [
    "RegisterRequest", "LoginRequest", "UserOut", "AuthResponse", "UpdateMeRequest",
    "AdminUserCreate", "AdminUserUpdate", "AdminUserOut",
    "AdminInvoiceCreate", "AdminInvoiceUpdate",
    "InvoiceValuesUpdate", "InvoiceOut", "OcrResultOut", "InvoiceUploadResponse", "InvoiceListResponse",
    "ConsommationDetaillee", "PrixUnitaire", "MontantDetaille",
    "DemandCreate", "DemandOut", "MyDemandOut", "AdminDemandOut", "DemandDecision",
    "AuditOut",
    "DashboardStats",
]
