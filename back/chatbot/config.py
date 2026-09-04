"""Chatbot configuration — 4-model sequential fallback chain.

Priority order (tried one by one until one succeeds):
  1. Groq  → openai/gpt-oss-120b         (best SQL, primary)
  2. Groq  → llama-3.3-70b-versatile     (free tier, strong reasoning)
  3. Groq  → gemma2-9b-it                (lightweight, fast)
  4. OpenRouter → openrouter/auto        (auto-routes to best available)
  🛡 Local keyword matcher / HTML renderer (no API, never fails)
"""
import os

# ── API credentials ────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"

# ── 4-model sequential fallback chain ─────────────────────────────────────────
# Each entry is tried in order; the first successful response wins.
# Fields:
#   name        – human-readable label shown in the chatbot UI
#   url         – API endpoint
#   api_key     – bearer token
#   model_id    – model identifier sent in the request body
#   extra_headers – additional headers required by the provider (optional)
MODEL_CHAIN: list[dict] = [
    {
        "name": "openai/gpt-oss-120b (Groq)",
        "url": GROQ_API_URL,
        "api_key": GROQ_API_KEY,
        "model_id": os.getenv("GROQ_SQL_MODEL", "openai/gpt-oss-120b"),
        "extra_headers": {"User-Agent": "InvoiceFlow-Admin-Chatbot/1.0"},
    },
    {
        "name": "llama-3.3-70b-versatile (Groq)",
        "url": GROQ_API_URL,
        "api_key": GROQ_API_KEY,
        "model_id": "llama-3.3-70b-versatile",
        "extra_headers": {"User-Agent": "InvoiceFlow-Admin-Chatbot/1.0"},
    },
    {
        "name": "gemma2-9b-it (Groq)",
        "url": GROQ_API_URL,
        "api_key": GROQ_API_KEY,
        "model_id": "gemma2-9b-it",
        "extra_headers": {"User-Agent": "InvoiceFlow-Admin-Chatbot/1.0"},
    },
    {
        "name": "openrouter/auto (OpenRouter)",
        "url": OPENROUTER_API_URL,
        "api_key": OPENROUTER_API_KEY,
        "model_id": "openrouter/auto",
        "extra_headers": {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "InvoiceFlow Admin Chatbot",
        },
    },
]

# ── Backward-compatibility aliases ────────────────────────────────────────────
GROQ_SQL_MODEL: str = MODEL_CHAIN[0]["model_id"]
GROQ_SYNTH_MODEL: str = MODEL_CHAIN[0]["model_id"]
OPENROUTER_MODEL: str = "openrouter/auto"

# Legacy aliases (keep for any code that still imports them)
GEMINI_API_KEY = OPENROUTER_API_KEY
GEMINI_MODEL = OPENROUTER_MODEL
