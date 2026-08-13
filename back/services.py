"""Shared service helpers: file storage and audit logging.

Combines what was previously two separate service files:
  - file_service.py  → save_upload_file()
  - audit_service.py → create_audit_log()
"""
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from config import UPLOADS_DIR, settings
from models import AuditLog, Demand

SAVE_CHUNK_SIZE = 1024 * 1024  # 1 MiB


# ---------------------------------------------------------------------------
# File service
# ---------------------------------------------------------------------------

def _check_extension(filename: str) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(settings.ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext or 'none'}'. Allowed: {allowed}",
        )


def save_upload_file(upload: UploadFile) -> str:
    """Validate and persist the uploaded facture, returning its store-relative path."""
    filename = (upload.filename or "facture").strip()
    _check_extension(filename)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOADS_DIR / f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"

    size = 0
    try:
        with target.open("wb") as out:
            while chunk := upload.file.read(SAVE_CHUNK_SIZE):
                size += len(chunk)
                if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit",
                    )
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception:
        target.unlink(missing_ok=True)
        raise

    return str(target.relative_to(UPLOADS_DIR.parent))


# ---------------------------------------------------------------------------
# Audit service
# ---------------------------------------------------------------------------

def create_audit_log(
    db: Session,
    *,
    demand: Demand,
    actor_id: int,
    action: str,
    field_changed: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> AuditLog:
    """Persist an audit trail row linked to the given demand."""
    entry = AuditLog(
        demand_id=demand.demand_id,
        action=action,
        actor_id=actor_id,
        field_changed=field_changed,
        old_value=old_value,
        new_value=new_value,
        timestamp=datetime.now(),
    )
    db.add(entry)
    return entry
