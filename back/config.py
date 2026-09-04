"""Application configuration.

All values can be overridden through environment variables so the backend
can be pointed at any SQL Server instance without code changes.
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

# Layout: back/ is the backend root, the frontend lives one level above.
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
# Store all scanned documents in one folder at the project root.
UPLOADS_DIR = PROJECT_DIR / "uploads"


def _detect_db_server() -> str:
    """Return the configured SQL Server host, defaulting to the InvoiceFlow instance."""
    return os.getenv("INVOICEFLOW_DB_SERVER", "SE7LLI")


class Settings:
    # ---- SQL Server connection (Windows / trusted auth) ----
    DB_SERVER: str = _detect_db_server()
    DB_NAME: str = os.getenv("INVOICEFLOW_DB_NAME", "StegDB")
    DB_DRIVER: str = os.getenv("INVOICEFLOW_DB_DRIVER", "ODBC Driver 18 for SQL Server")

    # ---- Auth (JWT) ----
    JWT_SECRET: str = os.getenv("INVOICEFLOW_JWT_SECRET", "invoiceflow-dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("INVOICEFLOW_JWT_EXPIRE_MINUTES", "720"))

    # ---- Upload constraints ----
    MAX_UPLOAD_MB: int = int(os.getenv("INVOICEFLOW_MAX_UPLOAD_MB", "10"))
    ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

    # ---- Roles / workflow statuses ----
    ROLES = {"user", "admin"}
    INVOICE_STATUSES = {"uploaded", "pending", "approved", "rejected"}
    DEMAND_STATUSES = {"pending", "approved", "rejected"}

    # ---- Server ----
    HOST: str = os.getenv("INVOICEFLOW_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("INVOICEFLOW_PORT", "8000"))
    SEED: bool = os.getenv("INVOICEFLOW_SEED", "0").lower() in {"1", "true", "yes"}

    # ---- Power BI Analytics (Publish to Web embed URL) ----
    POWERBI_EMBED_URL: str = os.getenv("POWERBI_EMBED_URL") or "https://app.powerbi.com/reportEmbed?reportId=96902f73-9b4c-4332-82a2-d5f389b4d82f&autoAuth=true&ctid=1ecd776d-d57f-4de0-a67a-eca9809e8d8d"

    def _odbc_connect(self, database: str) -> str:
        """Build an ODBC connection string for the given database."""
        return (
            f"DRIVER={{{self.DB_DRIVER}}};"
            f"SERVER={self.DB_SERVER};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
        )

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL using odbc_connect for the configured SQL Server instance."""
        conn_str = self._odbc_connect(self.DB_NAME)
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"

    @property
    def master_url(self) -> str:
        """Connection URL to master (used to create the database when missing)."""
        conn_str = self._odbc_connect("master")
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"


settings = Settings()
