"""Idempotent seed of demo accounts and sample invoices for the overview demo.

Demo accounts (password: ``demo123``):
  - sami.rejeb@steg.tn        (user / demo)
  - admin.validation@steg.tn  (admin)
"""
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AuditLog, Demand, Invoice, User
from security import hash_password

DEMO_PASSWORD = "demo123"
DEMO_USER_EMAIL = "sami.rejeb@steg.tn"
DEMO_ADMIN_EMAIL = "admin.validation@steg.tn"

SAMPLE_INVOICES = [
    {
        "invoice_no": "2026-STEG-77491",
        "invoice_date": date(2026, 7, 1),
        "amount_excl_tax": 320.000,
        "tva": 64.450,
        "amount_incl_tax": 384.450,
        "kwh_consumed": 1230,
        "due_date": date(2026, 8, 25),
        "status": "pending",
        "demand_status": "pending",
        "demand_reviewed": False,
    },
    {
        "invoice_no": "2026-STEG-55120",
        "invoice_date": date(2026, 5, 1),
        "amount_excl_tax": 288.100,
        "tva": 57.700,
        "amount_incl_tax": 345.800,
        "kwh_consumed": 1150,
        "due_date": date(2026, 6, 20),
        "status": "validated",
        "demand_status": "validated",
        "demand_reviewed": True,
    },
    {
        "invoice_no": "2026-STEG-33910",
        "invoice_date": date(2026, 3, 1),
        "amount_excl_tax": 248.800,
        "tva": 49.800,
        "amount_incl_tax": 298.600,
        "kwh_consumed": 1050,
        "due_date": date(2026, 4, 15),
        "status": "validated",
        "demand_status": "validated",
        "demand_reviewed": True,
    },
]


def _get_or_create_user(db: Session, name: str, email: str, role: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            full_name=name,
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=role,
            account_status="active",
        )
        db.add(user)
        db.flush()
    elif user.account_status != "active" or user.role != role:
        # Demo accounts must always remain usable (re-activate if a previous
        # migration defaulted them to 'pending', or re-apply the demo role).
        user.account_status = "active"
        user.role = role
        db.flush()
    return user


def seed(db: Session) -> None:
    """Seed demo users + sample invoices the first time the DB is empty."""
    demo_user = _get_or_create_user(db, "Sami Rejeb", DEMO_USER_EMAIL, "user")
    admin_user = _get_or_create_user(db, "Admin Master (STEG)", DEMO_ADMIN_EMAIL, "admin")
    db.commit()

    if db.scalar(
        select(func.count(Invoice.invoice_id)).where(Invoice.user_id == demo_user.user_id)
    ) > 0:
        return

    for idx, spec in enumerate(SAMPLE_INVOICES, start=1):
        month = 8 - idx
        invoice = Invoice(
            user_id=demo_user.user_id,
            file_path=f"uploads/sample/steg_{spec['invoice_no']}.pdf",
            invoice_no=spec["invoice_no"],
            invoice_date=spec["invoice_date"],
            amount_excl_tax=spec["amount_excl_tax"],
            tva=spec["tva"],
            amount_incl_tax=spec["amount_incl_tax"],
            kwh_consumed=spec["kwh_consumed"],
            due_date=spec["due_date"],
            currency="TND",
            supplier="STEG",
            status=spec["status"],
            uploaded_at=datetime(2026, month, 3, 9, 20),
        )
        db.add(invoice)
        db.flush()

        demand = Demand(
            invoice_id=invoice.invoice_id,
            user_id=demo_user.user_id,
            status=spec["demand_status"],
            submitted_at=datetime(2026, month, 5, 14, 15),
        )
        db.add(demand)
        db.flush()
        if spec["demand_reviewed"]:
            demand.reviewed_by_admin_id = admin_user.user_id
            demand.reviewed_at = datetime(2026, month, 6, 11, 0)
            db.add(
                AuditLog(
                    demand_id=demand.demand_id,
                    action="VALIDATED_DEMAND",
                    actor_id=admin_user.user_id,
                    field_changed="status",
                    old_value="pending",
                    new_value="validated",
                    timestamp=datetime(2026, month, 6, 11, 0),
                )
            )
        db.add(demand)

    db.commit()
