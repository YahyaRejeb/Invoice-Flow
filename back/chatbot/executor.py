"""Database SQL Executor for RAG Chatbot queries."""
import logging
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("invoiceflow.chatbot.executor")


def execute_sql(sql_query: str, db: Session) -> List[Dict[str, Any]]:
    """Execute validated SELECT query against SQL Server database via Session."""
    try:
        result = db.execute(text(sql_query))
        keys = list(result.keys())
        rows = result.fetchall()

        results = []
        for r in rows:
            row_dict = {}
            for idx, key in enumerate(keys):
                val = r[idx]
                # Convert dates/datetimes to ISO strings
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif hasattr(val, "__float__"):
                    val = float(val)
                row_dict[key] = val
            results.append(row_dict)

        return results
    except Exception as err:
        logger.error("Error executing SQL query '%s': %s", sql_query, err)
        raise RuntimeError(f"Database query execution error: {err}")
