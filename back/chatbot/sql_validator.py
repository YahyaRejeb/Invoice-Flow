"""SQL Safety Validator for RAG Chatbot queries.

Ensures that generated SQL queries are strictly read-only SELECT statements
and blocks any destructive commands or dangerous syntax.
"""
import re
import logging

logger = logging.getLogger("invoiceflow.chatbot.sql_validator")

# Forbidden destructive keywords
FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "EXEC", "EXECUTE",
    "MERGE", "GRANT", "REVOKE", "CREATE", "SHUTDOWN", "ALTER TABLE", "DROP TABLE",
    "INTO", "WAITFOR", "XP_CMDSHELL"
}


def validate_sql(sql_query: str) -> tuple[bool, str]:
    """Validate that the query is a safe, read-only SELECT statement."""
    if not sql_query or not sql_query.strip():
        return False, "SQL query is empty."

    cleaned = sql_query.strip()
    upper_query = cleaned.upper()

    # Must start with SELECT or WITH
    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
        return False, "Only read-only SELECT queries are allowed."

    # Check for forbidden keywords (tokenized)
    words = set(re.findall(r"\b[A-Z_]+\b", upper_query))
    forbidden_matches = words.intersection(FORBIDDEN_KEYWORDS)
    if forbidden_matches:
        logger.warning("Blocked SQL containing forbidden keywords: %s", forbidden_matches)
        return False, f"Forbidden SQL keywords detected: {', '.join(forbidden_matches)}"

    # Check for multiple statements (semicolon injection)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements are not permitted."

    return True, "Valid SQL"
