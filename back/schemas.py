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
    invoice_no: str | None = Field(default=None, max_length=50)
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    tva: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    amount_incl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    currency: str = Field(default="TND", max_length=10)
    kwh_consumed: int | None = Field(default=None, ge=0)
    due_date: date | None = None
    status: str = Field(default="uploaded", pattern="^(uploaded|validated_by_user|pending|validated|rejected)$")


class AdminInvoiceUpdate(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    file_path: str | None = Field(default=None, min_length=1, max_length=500)
    supplier: str | None = Field(default=None, max_length=100)
    invoice_no: str | None = Field(default=None, max_length=50)
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    tva: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    amount_incl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    currency: str | None = Field(default=None, max_length=10)
    kwh_consumed: int | None = Field(default=None, ge=0)
    due_date: date | None = None
    status: str | None = Field(default=None, pattern="^(uploaded|validated_by_user|pending|validated|rejected)$")


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceValuesUpdate(BaseModel):
    """Validated fields the user confirms after reviewing the OCR output."""

    supplier: str = Field(default="STEG", max_length=100)
    invoice_no: str | None = Field(default=None, max_length=50)
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    tva: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    amount_incl_tax: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    currency: str = Field(default="TND", max_length=10)
    kwh_consumed: int | None = Field(default=None, ge=0)
    due_date: date | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: int
    user_id: int
    file_name: str | None = None
    supplier: str | None = None
    invoice_no: str | None = None
    invoice_date: date | None = None
    amount_excl_tax: Decimal | None = None
    tva: Decimal | None = None
    amount_incl_tax: Decimal | None = None
    currency: str | None = None
    kwh_consumed: int | None = None
    due_date: date | None = None
    status: str | None = None
    uploaded_at: datetime | None = None
    demand_id: int | None = None
    demand_status: str | None = None
    user_name: str | None = None
    user_email: str | None = None


class InvoiceUploadResponse(BaseModel):
    invoice: InvoiceOut
    message: str = "Upload successful. Awaiting value validation."


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
    amount_incl_tax: Decimal | None = None
    status: str
    submitted_at: datetime


class AdminDemandOut(MyDemandOut):
    """Demand enriched with requester identity, for the admin review queue."""

    user_id: int
    user_name: str | None = None
    user_email: str | None = None


class DemandDecision(BaseModel):
    status: str = Field(pattern="^(validated|rejected)$")


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
    "InvoiceValuesUpdate", "InvoiceOut", "InvoiceUploadResponse", "InvoiceListResponse",
    "DemandCreate", "DemandOut", "MyDemandOut", "AdminDemandOut", "DemandDecision",
    "AuditOut",
    "DashboardStats",
]
