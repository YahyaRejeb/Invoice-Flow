"""Idempotent seed of demo accounts for the overview demo.

Demo accounts (password: ``demo123``):
  - sami.rejeb@invoiceflow.tn        (user / demo)
  - admin.validation@invoiceflow.tn  (admin)
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import User
from security import hash_password

DEMO_PASSWORD = "demo123"
DEMO_USER_EMAIL = "sami.rejeb@invoiceflow.tn"
DEMO_ADMIN_EMAIL = "admin.validation@invoiceflow.tn"

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
    """Seed only the demo accounts; invoice samples are intentionally disabled."""
    _get_or_create_user(db, "Sami Rejeb", DEMO_USER_EMAIL, "user")
    _get_or_create_user(db, "Admin Master (InvoiceFlow)", DEMO_ADMIN_EMAIL, "admin")
    db.commit()
