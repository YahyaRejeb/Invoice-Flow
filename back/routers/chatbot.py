"""RAG AI Admin Chatbot Router.

Provides direct, authenticated database context retrieval and intelligent assistant answers
for system administrators querying Users, Invoices, Demands, and Admin Informations.
"""
import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from chatbot.config import GROQ_SQL_MODEL
from chatbot.service import process_chat_query
from database import get_db
from deps import require_admin
from models import AuditLog, Demand, Invoice, User

logger = logging.getLogger("invoiceflow.router.chatbot")

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

DbDep = Annotated[Session, Depends(get_db)]


class ChatQueryInput(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None


class ChatQueryOutput(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    sources: List[str]
    intent: str
    timestamp: str


@router.get("/status")
def get_chatbot_status(db: DbDep, current_user: User = Depends(require_admin)):
    """Return RAG system indexing health and entity counts for admin."""
    user_count = db.scalar(select(func.count(User.user_id))) or 0
    invoice_count = db.scalar(select(func.count(Invoice.invoice_id))) or 0
    demand_count = db.scalar(select(func.count(Demand.demand_id))) or 0
    audit_count = db.scalar(select(func.count(AuditLog.audit_id))) or 0

    return {
        "status": "online",
        "engine": f"InvoiceFlow {GROQ_SQL_MODEL} Text-to-SQL RAG Engine",
        "indexed_entities": user_count + invoice_count + demand_count + audit_count,
        "counts": {
            "users": user_count,
            "invoices": invoice_count,
            "demands": demand_count,
            "audit_logs": audit_count,
        },
        "tables": ["Users", "Invoices", "Demands", "AuditLogs"],
    }


@router.post("/query", response_model=ChatQueryOutput)
def query_chatbot(
    payload: ChatQueryInput,
    db: DbDep,
    current_user: User = Depends(require_admin),
):
    """Query the RAG engine for user management, invoice statistics, or admin informations."""
    user_msg = payload.message.strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Query message cannot be empty."
        )

    res = process_chat_query(user_msg, db, current_user)

    return ChatQueryOutput(
        answer=res["answer"],
        sql_query=res.get("sql_query"),
        sources=res.get("sources", [GROQ_SQL_MODEL]),
        intent=res.get("intent", "text_to_sql"),
        timestamp=res["timestamp"],
    )
