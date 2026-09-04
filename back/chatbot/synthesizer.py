"""Groq Answer Synthesizer module — 4-model sequential fallback chain.

Translates executed database query results into friendly natural language
and HTML tables. Tries each model in MODEL_CHAIN in order; falls back to
a built-in HTML table renderer if all API calls fail.
"""
import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

from chatbot.config import MODEL_CHAIN
from chatbot.prompts import SYSTEM_PROMPT_SYNTHESIZE_ANSWER

logger = logging.getLogger("invoiceflow.chatbot.synthesizer")


# ── Generic single-model caller ───────────────────────────────────────────────

def _call_api(model_cfg: dict, messages: list, temperature: float, max_tokens: int) -> Optional[str]:
    """Call one model endpoint and return the text content, or None on failure."""
    payload = {
        "model": model_cfg["model_id"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {model_cfg['api_key']}",
    }
    headers.update(model_cfg.get("extra_headers", {}))

    req = urllib.request.Request(
        model_cfg["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status == 200:
            res_json = json.loads(resp.read().decode("utf-8"))
            choices = res_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
    return None


# ── Public entry point ────────────────────────────────────────────────────────

def synthesize_answer(
    user_question: str,
    sql_query: str,
    query_results: List[Dict[str, Any]],
) -> tuple[str, str]:
    """Compose a natural language answer from database query results.

    Returns:
        (answer_string, model_name_used) — model_name_used is the human-readable
        label of whichever model succeeded, or 'Local Renderer' if none did.
    """
    data_summary = json.dumps(query_results[:30], default=str)
    user_prompt = (
        f"USER QUESTION: {user_question}\n"
        f"EXECUTED SQL: {sql_query}\n"
        f"DATABASE RESULTS ({len(query_results)} rows):\n{data_summary}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SYNTHESIZE_ANSWER},
        {"role": "user", "content": user_prompt},
    ]

    for model_cfg in MODEL_CHAIN:
        try:
            answer = _call_api(model_cfg, messages, temperature=0.3, max_tokens=1200)
            if answer:
                logger.info("Answer synthesized by %s", model_cfg["name"])
                return answer, model_cfg["name"]
        except Exception as err:
            logger.warning(
                "Model '%s' failed for synthesis, trying next: %s",
                model_cfg["name"], err,
            )

    # All API models failed → built-in HTML renderer
    logger.error("All API models failed; using built-in HTML table renderer.")
    return _fallback_synthesize_answer(user_question, sql_query, query_results), "Local Renderer"


# ── Built-in fallback renderer ────────────────────────────────────────────────

def _fallback_synthesize_answer(
    user_question: str,
    sql_query: str,
    query_results: List[Dict[str, Any]],
) -> str:
    """Built-in elegant renderer for database query results — no API required."""
    if not query_results:
        return "ℹ️ <strong>Query Executed</strong><br><br>No matching records found in the database for your query."

    headers = list(query_results[0].keys())
    table_headers = "".join([f"<th>{h.replace('_', ' ').title()}</th>" for h in headers])
    table_rows = []

    for row in query_results[:20]:
        tds = []
        for h in headers:
            val = row[h]
            if val is None:
                val = "-"
            elif isinstance(val, float):
                val = f"{val:,.3f}"
            elif isinstance(val, str) and val.lower() in ["active", "approved"]:
                val = f"<span class='badge badge-{val.lower()}'>{val.upper()}</span>"
            elif isinstance(val, str) and val.lower() in ["pending", "pending_review"]:
                val = f"<span class='badge badge-pending'>{val.upper()}</span>"
            elif isinstance(val, str) and val.lower() in ["inactive", "rejected"]:
                val = f"<span class='badge' style='background:rgba(239,68,68,0.15); color:#ef4444;'>{val.upper()}</span>"
            tds.append(f"<td>{val}</td>")
        table_rows.append(f"<tr>{''.join(tds)}</tr>")

    return (
        f"📊 <strong>Database Query Results</strong><br><br>"
        f"Retrieved <strong>{len(query_results)} record(s)</strong> from SQL Server:<br><br>"
        f"<table class='chat-table'>"
        f"<thead><tr>{table_headers}</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        f"</table>"
    )
