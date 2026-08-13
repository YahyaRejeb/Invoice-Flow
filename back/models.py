"""ORM models for the STEG Facture Processing Platform.

All SQLAlchemy table definitions live here so every model is registered
on ``Base.metadata`` with a single import.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """Accounts and roles. Maps to the existing [Users] table in StegDB."""

    __tablename__ = "Users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'user'"))
    account_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("getdate()")
    )

    invoices = relationship("Invoice", back_populates="owner", cascade="all, delete-orphan")
    demands = relationship(
        "Demand",
        back_populates="requester",
        foreign_keys="Demand.user_id",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class Invoice(Base):
    """One row per uploaded facture, tracking raw file + validated values.

    Maps to the existing [Invoices] table in StegDB. ``kwh_consumed`` and
    ``due_date`` are added by the backend's additive migration.
    """

    __tablename__ = "Invoices"

    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Users.user_id"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    supplier: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'STEG'")
    )
    invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_excl_tax: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    tva: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    amount_incl_tax: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'TND'")
    )
    kwh_consumed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'uploaded'"), index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("getdate()")
    )

    owner = relationship("User", back_populates="invoices")
    demand = relationship(
        "Demand",
        back_populates="invoice",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def file_name(self) -> str:
        import os
        return os.path.basename(self.file_path)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.invoice_id} status={self.status}>"


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------

class Demand(Base):
    """Formal administrative demand tied to an invoice, tracked through review.

    Maps to the existing [Demands] table in StegDB.
    """

    __tablename__ = "Demands"

    demand_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Invoices.invoice_id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Users.user_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'"), index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("getdate()")
    )
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Users.user_id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    invoice = relationship("Invoice", back_populates="demand")
    requester = relationship(
        "User",
        back_populates="demands",
        foreign_keys="Demand.user_id",
    )
    reviewing_admin = relationship("User", foreign_keys="Demand.reviewed_by_admin_id")
    audit_logs = relationship("AuditLog", back_populates="demand", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Demand {self.demand_id} status={self.status}>"


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """Traceability of user corrections and admin decisions.

    Maps to the existing [AuditLogs] table in StegDB.
    """

    __tablename__ = "AuditLogs"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    demand_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Demands.demand_id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Users.user_id"), nullable=False
    )
    field_changed: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("getdate()")
    )

    demand = relationship("Demand", back_populates="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.audit_id} action={self.action}>"


__all__ = ["Base", "User", "Invoice", "Demand", "AuditLog"]
