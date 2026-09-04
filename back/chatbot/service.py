"""Main RAG Chatbot Service Manager.

Orchestrates:
  User question → generate_sql() → validate_sql() → execute_sql() → synthesize_answer() → Final Response
"""
import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from chatbot.executor import execute_sql
from chatbot.sql_generator import generate_sql
from chatbot.sql_validator import validate_sql
from chatbot.synthesizer import synthesize_answer
from models import User

logger = logging.getLogger("invoiceflow.chatbot.service")


def process_chat_query(user_question: str, db: Session, current_user: User) -> Dict[str, Any]:
    """Execute full RAG Text-to-SQL Pipeline for admin query."""
    logger.info("Processing admin chat query from %s: '%s'", current_user.email, user_question)

    # Step 1: Generate SQL or Conversational response
    raw_response, sql_model = generate_sql(user_question)
    cleaned_upper = raw_response.strip().upper()

    # Check if the output is a database SQL query (starts with SELECT or WITH)
    is_sql_query = cleaned_upper.startswith("SELECT") or cleaned_upper.startswith("WITH")

    if not is_sql_query:
        # Conversational answer (e.g. "Who are you?")
        return {
            "answer": raw_response,
            "sql_query": None,
            "sources": [sql_model],
            "intent": "conversational",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # Step 2: Validate SQL safety
    is_valid, validation_msg = validate_sql(raw_response)
    if not is_valid:
        logger.warning("SQL validation failed: %s", validation_msg)
        return {
            "answer": f"⚠️ <strong>Security Restriction</strong><br><br>{validation_msg}",
            "sql_query": raw_response,
            "sources": ["SQL Safety Validator"],
            "intent": "blocked_query",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # Step 3: Execute SQL on SQL Server DB
    try:
        query_results = execute_sql(raw_response, db)
    except Exception as err:
        logger.error("DB Execution error: %s", err)
        return {
            "answer": f"⚠️ <strong>Database Execution Error</strong><br><br><code>{err}</code>",
            "sql_query": raw_response,
            "sources": [sql_model, "SQL Server DB"],
            "intent": "db_error",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # Step 4: Synthesize Final Answer
    final_answer, synth_model = synthesize_answer(user_question, raw_response, query_results)

    return {
        "answer": final_answer,
        "sql_query": raw_response,
        "sources": [sql_model, "SQL Server DB"],
        "intent": "text_to_sql",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
