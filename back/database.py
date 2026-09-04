"""Database engine, session factory and startup bootstrap.

- Connects to SQL Server (Windows trusted auth) on the SE7LLI instance by
  default, against the existing StegDB schema.
- Creates StegDB automatically the first time if it is missing.
- Runs idempotent additive migrations (nothing destructive) so the tables stay
  compatible with the frontend even after the schema was built manually in SSMS.
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings, UPLOADS_DIR

logger = logging.getLogger("invoiceflow.database")

MIGRATIONS = (
    # Extra columns used by the frontend/dashboard that are not in the manually
    # created Invoices table yet. Both are additive and safe to re-run.
    "IF COL_LENGTH('dbo.Invoices', 'kwh_consumed') IS NULL "
    "ALTER TABLE [Invoices] ADD [kwh_consumed] INT NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'address') IS NULL "
    "ALTER TABLE [Invoices] ADD [address] NVARCHAR(255) NULL;",
    "IF COL_LENGTH('dbo.Users', 'account_status') IS NULL "
    "ALTER TABLE [Users] ADD [account_status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_Users_account_status] DEFAULT 'pending';",
    # Backfill: map legacy Users.status to new account_status.
    # 'active' -> 'active' (keeps existing active users active).
    # 'waiting' and NULL remain 'pending' (default) -> user must be approved by admin.
    # NOTE: wrapped in sp_executesql so SQL Server only resolves the [status]
    # column reference at *runtime* (after the COL_LENGTH guard), not at parse time.
    "IF COL_LENGTH('dbo.Users', 'account_status') IS NOT NULL "
    "AND COL_LENGTH('dbo.Users', 'status') IS NOT NULL "
    "EXEC sp_executesql N'UPDATE [Users] SET [account_status] = ''active'' WHERE [status] = ''active'';';",
    # Switch timestamp defaults from UTC (sysutcdatetime) to local server time (getdate).
    # Drop any existing default constraint on the column, then add the local-time default.
    # These are idempotent: re-running drops the current default and re-adds getdate().
    """
DECLARE @cn sysname;
SELECT @cn = dc.name FROM sys.default_constraints dc
JOIN sys.columns c ON c.default_object_id = dc.object_id
WHERE dc.parent_object_id = OBJECT_ID('dbo.Users') AND c.name = 'created_at';
IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[Users] DROP CONSTRAINT [' + @cn + ']');
ALTER TABLE [dbo].[Users] ADD CONSTRAINT [DF_Users_created_at_local] DEFAULT (getdate()) FOR [created_at];
""",
    """
DECLARE @cn sysname;
SELECT @cn = dc.name FROM sys.default_constraints dc
JOIN sys.columns c ON c.default_object_id = dc.object_id
WHERE dc.parent_object_id = OBJECT_ID('dbo.Invoices') AND c.name = 'uploaded_at';
IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[Invoices] DROP CONSTRAINT [' + @cn + ']');
ALTER TABLE [dbo].[Invoices] ADD CONSTRAINT [DF_Invoices_uploaded_at_local] DEFAULT (getdate()) FOR [uploaded_at];
""",
    """
DECLARE @cn sysname;
SELECT @cn = dc.name FROM sys.default_constraints dc
JOIN sys.columns c ON c.default_object_id = dc.object_id
WHERE dc.parent_object_id = OBJECT_ID('dbo.Demands') AND c.name = 'submitted_at';
IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[Demands] DROP CONSTRAINT [' + @cn + ']');
ALTER TABLE [dbo].[Demands] ADD CONSTRAINT [DF_Demands_submitted_at_local] DEFAULT (getdate()) FOR [submitted_at];
""",
    """
DECLARE @cn sysname;
SELECT @cn = dc.name FROM sys.default_constraints dc
JOIN sys.columns c ON c.default_object_id = dc.object_id
WHERE dc.parent_object_id = OBJECT_ID('dbo.AuditLogs') AND c.name = 'timestamp';
IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[AuditLogs] DROP CONSTRAINT [' + @cn + ']');
ALTER TABLE [dbo].[AuditLogs] ADD CONSTRAINT [DF_AuditLogs_timestamp_local] DEFAULT (getdate()) FOR [timestamp];
""",
    # -----------------------------------------------------------------
    # InvoiceFlow OCR Expansion: detailed tariff breakdown columns
    # -----------------------------------------------------------------
    # Consommation per tariff period (INTEGER)
    "IF COL_LENGTH('dbo.Invoices', 'consumption_jour') IS NULL "
    "ALTER TABLE [Invoices] ADD [consumption_jour] INT NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'consumption_pointe') IS NULL "
    "ALTER TABLE [Invoices] ADD [consumption_pointe] INT NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'consumption_soiree') IS NULL "
    "ALTER TABLE [Invoices] ADD [consumption_soiree] INT NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'consumption_nuit') IS NULL "
    "ALTER TABLE [Invoices] ADD [consumption_nuit] INT NULL;",
    # Prix Unitaire per tariff period (DECIMAL 12,3 — NOT FLOAT)
    "IF COL_LENGTH('dbo.Invoices', 'pu_jour') IS NULL "
    "ALTER TABLE [Invoices] ADD [pu_jour] DECIMAL(12,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'pu_pointe') IS NULL "
    "ALTER TABLE [Invoices] ADD [pu_pointe] DECIMAL(12,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'pu_soiree') IS NULL "
    "ALTER TABLE [Invoices] ADD [pu_soiree] DECIMAL(12,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'pu_nuit') IS NULL "
    "ALTER TABLE [Invoices] ADD [pu_nuit] DECIMAL(12,3) NULL;",
    # Detailed Montant per tariff period (DECIMAL 15,3 — NOT FLOAT)
    "IF COL_LENGTH('dbo.Invoices', 'montant_jour') IS NULL "
    "ALTER TABLE [Invoices] ADD [montant_jour] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'montant_pointe') IS NULL "
    "ALTER TABLE [Invoices] ADD [montant_pointe] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'montant_soiree') IS NULL "
    "ALTER TABLE [Invoices] ADD [montant_soiree] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'montant_nuit') IS NULL "
    "ALTER TABLE [Invoices] ADD [montant_nuit] DECIMAL(15,3) NULL;",
    # Summary monetary rows (DECIMAL 15,3 — NOT FLOAT)
    "IF COL_LENGTH('dbo.Invoices', 'sous_total') IS NULL "
    "ALTER TABLE [Invoices] ADD [sous_total] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'total_1') IS NULL "
    "ALTER TABLE [Invoices] ADD [total_1] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'total_2') IS NULL "
    "ALTER TABLE [Invoices] ADD [total_2] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'total_3') IS NULL "
    "ALTER TABLE [Invoices] ADD [total_3] DECIMAL(15,3) NULL;",
    "IF COL_LENGTH('dbo.Invoices', 'net_a_payer') IS NULL "
    "ALTER TABLE [Invoices] ADD [net_a_payer] DECIMAL(15,3) NULL;",
    # Backfill the aggregate consumption for invoices created before the OCR
    # calculation was added. Re-running is harmless because only zero/NULL
    # aggregates are corrected.
    "UPDATE [dbo].[Invoices] "
    "SET [kwh_consumed] = COALESCE([consumption_jour], 0) "
    "+ COALESCE([consumption_pointe], 0) "
    "+ COALESCE([consumption_soiree], 0) "
    "+ COALESCE([consumption_nuit], 0) "
    "WHERE [kwh_consumed] IS NULL OR [kwh_consumed] = 0;",
    # Remove the old demo invoice rows and their dependent workflow records.
    "DELETE al FROM [dbo].[AuditLogs] al "
    "INNER JOIN [dbo].[Demands] d ON d.demand_id = al.demand_id "
    "INNER JOIN [dbo].[Invoices] i ON i.invoice_id = d.invoice_id "
    "WHERE i.invoice_no IN ('2026-INV-77491', '2026-INV-55120', '2026-INV-33910');",
    "DELETE d FROM [dbo].[Demands] d "
    "INNER JOIN [dbo].[Invoices] i ON i.invoice_id = d.invoice_id "
    "WHERE i.invoice_no IN ('2026-INV-77491', '2026-INV-55120', '2026-INV-33910');",
    "DELETE FROM [dbo].[Invoices] "
    "WHERE invoice_no IN ('2026-INV-77491', '2026-INV-55120', '2026-INV-33910');",
)



class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
    connect_args={
        "timeout": 10,
        "autocommit": False,
    },
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency providing a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_database_exists() -> None:
    """Create the StegDB database if it does not exist yet (no-op otherwise)."""
    master = create_engine(
        settings.master_url,
        future=True,
        connect_args={"timeout": 10, "autocommit": True},
    )
    try:
        with master.connect() as conn:
            exists = conn.execute(
                text("SELECT COUNT(*) FROM sys.databases WHERE name = :name"),
                {"name": settings.DB_NAME},
            ).scalar()
            if not exists:
                conn.execute(text(f"CREATE DATABASE [{settings.DB_NAME}]"))
                logger.info("Created database %s", settings.DB_NAME)
    finally:
        master.dispose()


def run_migrations() -> None:
    """Apply additive migrations (idempotent)."""
    with engine.begin() as conn:
        for statement in MIGRATIONS:
            conn.execute(text(statement))
    logger.info("Schema migrations applied")


def cleanup_demo_data() -> None:
    """Remove stale demo invoices and related workflow rows inserted during testing."""
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE al
            FROM [dbo].[AuditLogs] al
            INNER JOIN [dbo].[Demands] d ON d.demand_id = al.demand_id
            INNER JOIN [dbo].[Invoices] i ON i.invoice_id = d.invoice_id
            WHERE i.supplier = 'STEG'
              AND (
                    i.invoice_no LIKE '2026-INV-%'
                 OR i.invoice_no LIKE 'DEMO-%'
                 OR i.invoice_no LIKE 'SAMPLE-%'
                 OR i.invoice_no LIKE 'EXP-%'
              );
        """))
        conn.execute(text("""
            DELETE d
            FROM [dbo].[Demands] d
            INNER JOIN [dbo].[Invoices] i ON i.invoice_id = d.invoice_id
            WHERE i.supplier = 'STEG'
              AND (
                    i.invoice_no LIKE '2026-INV-%'
                 OR i.invoice_no LIKE 'DEMO-%'
                 OR i.invoice_no LIKE 'SAMPLE-%'
                 OR i.invoice_no LIKE 'EXP-%'
              );
        """))
        conn.execute(text("""
            DELETE FROM [dbo].[Invoices]
            WHERE supplier = 'STEG'
              AND (
                    invoice_no LIKE '2026-INV-%'
                 OR invoice_no LIKE 'DEMO-%'
                 OR invoice_no LIKE 'SAMPLE-%'
                 OR invoice_no LIKE 'EXP-%'
              );
        """))
    logger.info("Demo invoice data cleaned up")


def init_db() -> None:
    """Bootstrap the database: create tables, then apply additive migrations."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_database_exists()
    # Import ensures every ORM model is registered on Base.metadata.
    import models  # noqa: F401
    # Create any missing tables first so additive migrations can target them.
    Base.metadata.create_all(bind=engine)
    run_migrations()
    cleanup_demo_data()
    logger.info("StegDB ready (InvoiceFlow application)")
