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
UPLOADS_DIR = BACKEND_DIR / "uploads"


def _detect_db_server() -> str:
    """Return the configured SQL Server host, defaulting to LocalDB MSSQLLocalDB."""
    return os.getenv("STEG_DB_SERVER", "(localdb)\\MSSQLLocalDB")


class Settings:
    # ---- SQL Server connection (Windows / trusted auth) ----
    DB_SERVER: str = _detect_db_server()
    DB_NAME: str = os.getenv("STEG_DB_NAME", "StegDB")
    DB_DRIVER: str = os.getenv("STEG_DB_DRIVER", "ODBC Driver 18 for SQL Server")

    # ---- Auth (JWT) ----
    JWT_SECRET: str = os.getenv("STEG_JWT_SECRET", "steg-dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("STEG_JWT_EXPIRE_MINUTES", "720"))

    # ---- Upload constraints ----
    MAX_UPLOAD_MB: int = int(os.getenv("STEG_MAX_UPLOAD_MB", "10"))
    ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

    # ---- Roles / workflow statuses ----
    ROLES = {"user", "admin"}
    INVOICE_STATUSES = {"uploaded", "validated_by_user", "pending", "validated", "rejected"}
    DEMAND_STATUSES = {"pending", "validated", "rejected"}

    # ---- Server ----
    HOST: str = os.getenv("STEG_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("STEG_PORT", "8000"))
    SEED: bool = os.getenv("STEG_SEED", "1").lower() in {"1", "true", "yes"}

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
        """SQLAlchemy URL using odbc_connect (works for LocalDB and regular instances)."""
        conn_str = self._odbc_connect(self.DB_NAME)
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"

    @property
    def master_url(self) -> str:
        """Connection URL to master (used to create the database when missing)."""
        conn_str = self._odbc_connect("master")
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"


settings = Settings()