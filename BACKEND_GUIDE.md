# Backend Functional Guide

This document explains what each backend file does, what each main function is responsible for, and gives a concrete example for every definition.

## 1. Overall purpose of the backend

The backend is a FastAPI application for managing invoice processing, authentication, demand submission, admin review, dashboard statistics, and audit logging.

It supports:
- user registration and login
- invoice upload and validation
- demand submission for validated invoices
- admin approval/rejection of demands
- dashboard insights for users and admins
- audit trails for important workflow changes

---

## 2. Backend folder structure

- [back/main.py](back/main.py) — application entry point and router registration
- [back/config.py](back/config.py) — app configuration, environment variables, and database settings
- [back/database.py](back/database.py) — DB engine, sessions, migrations, and initialization
- [back/deps.py](back/deps.py) — authentication and authorization dependencies
- [back/models.py](back/models.py) — SQLAlchemy database models
- [back/schemas.py](back/schemas.py) — Pydantic request and response models
- [back/security.py](back/security.py) — password hashing and JWT handling
- [back/services.py](back/services.py) — file storage and audit logging helpers
- [back/seed.py](back/seed.py) — demo seed data for users and invoices
- [back/run.py](back/run.py) — simple startup script for running the app
- [back/routers/auth.py](back/routers/auth.py) — authentication endpoints
- [back/routers/invoices.py](back/routers/invoices.py) — invoice endpoints
- [back/routers/demands.py](back/routers/demands.py) — demand workflow endpoints
- [back/routers/admin.py](back/routers/admin.py) — admin review and audit endpoints
- [back/routers/dashboard.py](back/routers/dashboard.py) — dashboard statistics endpoints

---

## 3. File-by-file explanation

### [back/main.py](back/main.py)

This is the main FastAPI application file.

Functions:

- `lifespan(_app)`
  - Runs when the app starts.
  - Initializes the database.
  - Optionally seeds demo data if the configuration allows it.
  - Ensures the backend is ready before serving requests.

> **Example.** The lifespan runs automatically when you start the server:
> ```python
> from main import app          # app = FastAPI(lifespan=lifespan)
> uvicorn.run(app, host="127.0.0.1", port=8000)
> ```
> On startup it calls `init_db()` and, because `settings.SEED` is `True` by default, runs `seed(db)` (which creates the demo accounts and invoices).

- `health()`
  - Returns a simple health-check response.
  - Used to verify the backend is running.
  - Response contains status, service name, and version.

> **Example.** `GET /health`
> ```bash
> curl http://127.0.0.1:8000/health
> ```
> ```json
> {"status": "ok", "service": "steg-backend", "version": "1.0.0"}
> ```

- `index()`
  - Serves the root page of the application.
  - Returns the main HTML page so the frontend can load.

> **Example.** `GET /` returns the raw HTML of `index.html`:
> ```bash
> curl http://127.0.0.1:8000/
> ```
> Response is `FileResponse(INDEX_FILE)` — the HTML document rendered by the browser.

What the file does overall:
- Creates the FastAPI app.
- Enables CORS for frontend requests.
- Registers all router modules (`/auth`, `/invoices`, `/demands`, `/admin`, `/dashboard`).
- Exposes the health endpoint.
- Serves the frontend assets (`/front`, `/assets`), uploaded files (`/uploads`), and the root page.

---

### [back/config.py](back/config.py)

This file stores configuration values for the whole backend.

Functions:

- `_detect_db_server()`
  - Returns the configured SQL Server host, defaulting to **LocalDB `MSSQLLocalDB`** (`(localdb)\MSSQLLocalDB`).
  - Used when no database server is explicitly configured via `STEG_DB_SERVER`.
  - Helps the app run on Windows environments without manual SQL Server Express setup.

> **Example.**
> ```python
> from config import _detect_db_server
> print(_detect_db_server())            # -> "(localdb)\MSSQLLocalDB" (default)
> # With an environment variable set:
> # STEG_DB_SERVER="SQLSRV01" python -c "from config import _detect_db_server; print(_detect_db_server())"
> # -> "SQLSRV01"
> ```

Class:

- `Settings`
  - Holds all configurable settings such as:
    - database server name
    - database name
    - JWT secret and expiration
    - upload size limits
    - allowed upload file extensions
    - role names and workflow statuses
    - host and port for the server
    - whether seeding is enabled
  - Provides `_odbc_connect(database)` to build a Windows-trusted ODBC connection string for a given database.
  - Provides properties `database_url` and `master_url` so the app can connect to SQL Server via SQLAlchemy using `mssql+pyodbc:///?odbc_connect=...` (quote_plus-encoded ODBC string). This works for LocalDB and regular instances alike.

> **Example.** Reading settings and the generated connection URLs:
> ```python
> from config import settings
>
> settings.DB_NAME            # -> "StegDB"
> settings.MAX_UPLOAD_MB      # -> 10
> settings.ALLOWED_UPLOAD_EXTENSIONS  # -> {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
> settings.ROLES              # -> {"user", "admin"}
> settings.JWT_EXPIRE_MINUTES # -> 720
>
> print(settings.database_url)
> # mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC+Driver+18+for+SQL+Server%7D%3B...Trusted_Connection%3Dyes%3BTrustServerCertificate%3Dyes
>
> print(settings.master_url)
> # mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC+Driver+18+for+SQL+Server%7D%3B...DATABASE%3Dmaster...
> ```

What the file does overall:
- Centralizes application settings.
- Keeps sensitive or environment-specific values out of the code.
- Makes the project easier to configure across environments.

---

### [back/database.py](back/database.py)

This file manages the database connection and startup setup.

Variables and objects:

- `Base`
  - SQLAlchemy declarative base used for all ORM models.

> **Example.** Every model inherits from `Base`:
> ```python
> class User(Base):   # Base = database.Base
>     __tablename__ = "Users"
>     ...
> ```

- `engine`
  - SQLAlchemy database engine.
  - Connects to the configured SQL Server database (LocalDB `MSSQLLocalDB` by default via `settings.database_url`).

> **Example.** `engine` is built from `settings.database_url` with connection timeouts and connection-pool recycling:
> ```python
> engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=1800, ...)
> ```

- `SessionLocal`
  - Session factory used to create database sessions.

> **Example.**
> ```python
> db = SessionLocal()          # open a new session
> db.add(some_invoice)
> db.commit()
> db.close()                   # always close when done
> ```

Functions:

- `get_db()`
  - FastAPI dependency that creates a DB session for each request.
  - Ensures the session is closed properly after the request finishes.

> **Example.** Used as a FastAPI dependency in every router:
> ```python
> from database import get_db
>
> @router.get("/mine")
> def list_my_invoices(db: Session = Depends(get_db)):
>     ...   # db is auto-created and auto-closed by FastAPI
> ```

- `_ensure_database_exists()`
  - Checks whether the target database already exists.
  - Creates the database if it is missing.

> **Example.** First run against a fresh SQL Server:
> ```
> INFO steg.database: Created database StegDB
> ```
> On subsequent runs the database already exists, so it is a no-op.

- `run_migrations()`
  - Applies additive schema changes safely.
  - Adds missing columns if they are not present.
  - Designed to be safe to run repeatedly.
  - **Includes a backfill migration** that maps the legacy `Users.status` column to the new `account_status`:
    - `status = 'active'` → `account_status = 'active'` (keeps existing active users active).
    - `status = 'waiting'` or `NULL` → stays `pending` (default), requiring admin approval.
  - **Switches timestamp column defaults from UTC to local server time** by dropping any existing default constraint on `Users.created_at`, `Invoices.uploaded_at`, `Demands.submitted_at`, and `AuditLogs.timestamp`, then adding `DEFAULT (getdate())`. This ensures manual/SSMS inserts also get the local clock hour.

> **Example.** It runs each idempotent SQL statement in `MIGRATIONS`:
> ```sql
> -- Add missing columns to Invoices
> IF COL_LENGTH('dbo.Invoices', 'kwh_consumed') IS NULL
> ALTER TABLE [Invoices] ADD [kwh_consumed] INT NULL;
> IF COL_LENGTH('dbo.Invoices', 'due_date') IS NULL
> ALTER TABLE [Invoices] ADD [due_date] DATE NULL;
>
> -- Add account_status to Users
> IF COL_LENGTH('dbo.Users', 'account_status') IS NULL
> ALTER TABLE [Users] ADD [account_status] NVARCHAR(30) NOT NULL
>   CONSTRAINT [DF_Users_account_status] DEFAULT 'pending';
>
> -- Backfill: legacy status='active' -> account_status='active'
> IF COL_LENGTH('dbo.Users', 'account_status') IS NOT NULL
> AND COL_LENGTH('dbo.Users', 'status') IS NOT NULL
> UPDATE [Users] SET [account_status] = 'active' WHERE [status] = 'active';
>
> -- Switch timestamp defaults to local time (getdate)
> DECLARE @cn sysname;
> SELECT @cn = dc.name FROM sys.default_constraints dc
> JOIN sys.columns c ON c.default_object_id = dc.object_id
> WHERE dc.parent_object_id = OBJECT_ID('dbo.Users') AND c.name = 'created_at';
> IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[Users] DROP CONSTRAINT [' + @cn + ']');
> ALTER TABLE [dbo].[Users] ADD CONSTRAINT [DF_Users_created_at_local] DEFAULT (getdate()) FOR [created_at];
> 
> DECLARE @cn sysname;
> SELECT @cn = dc.name FROM sys.default_constraints dc
> JOIN sys.columns c ON c.default_object_id = dc.object_id
> WHERE dc.parent_object_id = OBJECT_ID('dbo.Invoices') AND c.name = 'uploaded_at';
> IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[Invoices] DROP CONSTRAINT [' + @cn + ']');
> ALTER TABLE [dbo].[Invoices] ADD CONSTRAINT [DF_Invoices_uploaded_at_local] DEFAULT (getdate()) FOR [uploaded_at];
> 
> DECLARE @cn sysname;
> SELECT @cn = dc.name FROM sys.default_constraints dc
> JOIN sys.columns c ON c.default_object_id = dc.object_id
> WHERE dc.parent_object_id = OBJECT_ID('dbo.Demands') AND c.name = 'submitted_at';
> IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[Demands] DROP CONSTRAINT [' + @cn + ']');
> ALTER TABLE [dbo].[Demands] ADD CONSTRAINT [DF_Demands_submitted_at_local] DEFAULT (getdate()) FOR [submitted_at];
> 
> DECLARE @cn sysname;
> SELECT @cn = dc.name FROM sys.default_constraints dc
> JOIN sys.columns c ON c.default_object_id = dc.object_id
> WHERE dc.parent_object_id = OBJECT_ID('dbo.AuditLogs') AND c.name = 'timestamp';
> IF @cn IS NOT NULL EXEC('ALTER TABLE [dbo].[AuditLogs] DROP CONSTRAINT [' + @cn + ']');
> ALTER TABLE [dbo].[AuditLogs] ADD CONSTRAINT [DF_AuditLogs_timestamp_local] DEFAULT (getdate()) FOR [timestamp];
> ```
> Re-running it never fails because the `IF COL_LENGTH(...) IS NULL` guards prevent duplicate columns, and the default-constraint swap is idempotent (drop + re-add).

- `init_db()`
  - Runs the full startup database bootstrap.
  - Creates the uploads folder.
  - Ensures the database exists.
  - Imports models so ORM metadata is registered.
  - Creates missing tables via `Base.metadata.create_all()`.
  - Applies additive migrations.

> **Example.** Called from the app lifespan at startup:
> ```python
> init_db()
> # logs:
> # INFO steg.database: Created database StegDB
> # INFO steg.database: Schema migrations applied
> # INFO steg.database: StegDB ready
> ```

What the file does overall:
- Connects the backend to SQL Server (LocalDB `MSSQLLocalDB` by default).
- Makes database access available to the app.
- Keeps the schema compatible with the frontend via idempotent migrations.

---

### [back/deps.py](back/deps.py)

This file contains reusable authentication dependencies.

Functions:

- `get_current_user(...)`
  - Reads the bearer token from the request.
  - Validates and decodes the JWT.
  - Loads the corresponding user from the database.
  - Rejects requests if the token is missing, invalid, expired, or points to a deleted user.

> **Example.** Used to protect a route:
> ```python
> from deps import get_current_user
>
> @router.get("/me", response_model=UserOut)
> def me(current_user: User = Depends(get_current_user)):
>     return current_user
> ```
> Calling it without a token:
> ```bash
> curl http://127.0.0.1:8000/auth/me
> ```
> ```json
> {"detail": "Missing authentication token"}
> ```
> With a valid token:
> ```bash
> curl -H "Authorization: Bearer <JWT>" http://127.0.0.1:8000/auth/me
> ```

- `require_admin(...)`
  - Ensures that only users with the admin role can call protected admin routes.
  - Returns the current user if authorized.
  - Throws a 403 error for non-admin users.

> **Example.**
> ```python
> from deps import require_admin
>
> @router.get("/admin/audit")
> def admin_audit_logs(admin: User = Depends(require_admin)):
>     ...
> ```
> A regular user calling an admin route gets:
> ```json
> {"detail": "Administrator privileges required"}
> ```

What the file does overall:
- Enforces authentication and role-based access control.
- Keeps authorization logic centralized and reusable.

---

### [back/models.py](back/models.py)

This file defines the SQLAlchemy ORM models.

Classes:

- `User`
  - Represents an application user.
  - Stores full name, email, password hash, role, and creation timestamp.
  - Has relationships to invoices and demands.

> **Example.** Creating a user row through the ORM:
> ```python
> user = User(full_name="Sami Rejeb", email="sami@steg.tn",
>             password_hash=hash_password("secret123"), role="user", account_status="active")
> db.add(user); db.commit(); db.refresh(user)
> print(user.user_id)   # -> 1
> ```
> | user_id | full_name   | email          | role  | account_status | created_at |
> |--------:|-------------|----------------|-------|----------------|------------|
> |       1 | Sami Rejeb  | sami@steg.tn   | user  | active         | 2026-08-11 ... |

- `Invoice`
  - Represents one uploaded invoice.
  - Stores the file path, supplier information, invoice numbers, dates, tax values, amount, currency, energy used, due date, and status.
  - Links to one user and optionally one demand.
  - Has a property `file_name` that extracts the file name from the stored path.

> **Example.**
> ```python
> invoice = Invoice(user_id=1, file_path="uploads/ab12cd34.pdf")
> db.add(invoice); db.commit()
>
> print(invoice.file_name)          # -> "ab12cd34.pdf"  (from the stored path)
> print(invoice.status)             # -> "uploaded"      (server default)
> print(invoice.currency)           # -> "TND"           (server default)
> ```
> | invoice_id | user_id | file_path        | supplier | status   |
> |-----------:|--------:|------------------|----------|----------|
> |          1 |       1 | uploads/ab12cd34.pdf | STEG  | uploaded |

- `Demand`
  - Represents a formal demand submitted for an invoice.
  - Stores status, submission time, reviewer, and review time.
  - Links to the invoice, requester, and audit logs.

> **Example.**
> ```python
> demand = Demand(invoice_id=1, user_id=1, status="pending")
> db.add(demand); db.commit()
> print(demand.status)      # -> "pending"
> print(demand.invoice)     # -> <Invoice 1 status=pending>
> ```

- `AuditLog`
  - Stores audit record entries for admin actions and workflow changes.
  - Useful for tracking who changed what and when.

> **Example.**
> ```python
> entry = AuditLog(demand_id=1, action="VALIDATED_DEMAND", actor_id=2,
>                  field_changed="status", old_value="pending", new_value="validated")
> db.add(entry); db.commit()
> ```
> | audit_id | demand_id | action           | actor_id | old_value | new_value |
> |---------:|----------:|------------------|---------:|-----------|-----------|
> |        1 |         1 | VALIDATED_DEMAND |        2 | pending   | validated |

What the file does overall:
- Defines the database schema in Python.
- Allows the backend to query and save application data using ORM objects.

---

### [back/schemas.py](back/schemas.py)

This file defines the request and response validation models used by FastAPI.

Key models:

- `RegisterRequest`
  - Validates registration input.
  - Requires full name, email, and password.
  - Trims the full name before saving.

> **Example.** Valid request body for `POST /auth/register`:
> ```json
> {"full_name": "  Amina Ben Ali  ", "email": "amina@steg.tn", "password": "secret123"}
> ```
> After validation, `full_name` is trimmed to `"Amina Ben Ali"`.
> A short name or bad email is rejected with a 422 error:
> ```json
> {"detail": [{"loc": ["body", "password"], "msg": "String should have at least 6 characters", "type": "string_too_short"}]}
> ```

- `LoginRequest`
  - Validates login input.
  - Requires email and password.

> **Example.** Body for `POST /auth/login`:
> ```json
> {"email": "amina@steg.tn", "password": "secret123"}
> ```

- `UserOut`
  - Represents the user data returned to the client.

> **Example.** Serialized user object:
> ```json
> {"user_id": 1, "full_name": "Amina Ben Ali", "email": "amina@steg.tn",
>  "role": "user", "account_status": "active", "created_at": "2026-08-11T09:00:00"}
> ```

- `AuthResponse`
  - Returned after login or registration.
  - Contains the JWT and user profile.

> **Example.** Full login response:
> ```json
> {"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6InVzZXIiLCJpYXQiOjE3ODg5MDAwMDAsImV4cCI6MTc4OTMzMjAwMH0.abc123...",
>  "token_type": "bearer",
>  "user": {"user_id": 1, "full_name": "Amina Ben Ali", "email": "amina@steg.tn",
>           "role": "user", "account_status": "active", "created_at": "2026-08-11T09:00:00"}}
> ```

- `InvoiceValuesUpdate`
  - Validates the user-confirmed invoice values after OCR review.
  - Includes supplier, invoice number, dates, amounts, currency, kwh, and due date.

> **Example.** Body for `PUT /invoices/1/values`:
> ```json
> {"supplier": "STEG", "invoice_no": "2026-STEG-77491", "invoice_date": "2026-07-01",
>  "amount_excl_tax": 320.0, "tva": 64.45, "amount_incl_tax": 384.45,
>  "currency": "TND", "kwh_consumed": 1230, "due_date": "2026-08-25"}
> ```

- `InvoiceOut`
  - Response schema for invoice details.
  - Can include demand relationship data.

> **Example.** Serialized invoice (with demand info merged in by `_invoice_out`):
> ```json
> {"invoice_id": 1, "user_id": 1, "file_name": "ab12cd34.pdf", "supplier": "STEG",
>  "invoice_no": "2026-STEG-77491", "invoice_date": "2026-07-01",
>  "amount_excl_tax": 320.0, "tva": 64.45, "amount_incl_tax": 384.45,
>  "currency": "TND", "kwh_consumed": 1230, "due_date": "2026-08-25",
>  "status": "pending", "uploaded_at": "2026-08-11T09:00:00",
>  "demand_id": 1, "demand_status": "pending"}
> ```

- `InvoiceUploadResponse`
  - Returned after invoice upload.
  - Contains the created invoice and a confirmation message.

> **Example.** Response of `POST /invoices/upload`:
> ```json
> {"invoice": {"invoice_id": 1, "user_id": 1, "file_name": "ab12cd34.pdf",
>              "supplier": "STEG", "status": "uploaded", "...": "..."},
>  "message": "Upload successful. Awaiting value validation."}
> ```

- `InvoiceListResponse`
  - Wraps a list of invoices and the total count.

> **Example.** Response of `GET /invoices/mine`:
> ```json
> {"invoices": [{"invoice_id": 1, "...": "..."}, {"invoice_id": 2, "...": "..."}], "total": 2}
> ```

- `DemandCreate`
  - Validates the payload for creating a demand.

> **Example.** Body for `POST /demands`:
> ```json
> {"invoice_id": 1}
> ```

- `DemandOut`
  - Represents a demand record in normal API responses.

> **Example.**
> ```json
> {"demand_id": 1, "invoice_id": 1, "user_id": 1, "status": "pending",
>  "submitted_at": "2026-08-11T09:30:00", "reviewed_by_admin_id": null, "reviewed_at": null}
> ```

- `MyDemandOut`
  - A richer demand view for the current user.

> **Example.** Response of `GET /demands/mine`:
> ```json
> {"demand_id": 1, "invoice_id": 1, "invoice_no": "2026-STEG-77491",
>  "supplier": "STEG", "amount_incl_tax": 384.45, "status": "pending",
>  "submitted_at": "2026-08-11T09:30:00"}
> ```

- `AdminDemandOut`
  - A richer demand view for admin review screens.

> **Example.** Item in the admin review queue (`GET /admin/demands`):
> ```json
> {"demand_id": 1, "invoice_id": 1, "invoice_no": "2026-STEG-77491",
>  "supplier": "STEG", "amount_incl_tax": 384.45, "status": "pending",
>  "submitted_at": "2026-08-11T09:30:00",
>  "user_id": 1, "user_name": "Amina Ben Ali", "user_email": "amina@steg.tn"}
> ```

- `DemandDecision`
  - Validates the admin decision payload for approve/reject requests.

> **Example.** Body for `PATCH /admin/demands/1`:
> ```json
> {"status": "validated"}
> ```
> Only `"validated"` or `"rejected"` are accepted.

- `AuditOut`
  - Represents an audit log entry.

> **Example.** Response of `GET /admin/audit`:
> ```json
> {"audit_id": 1, "demand_id": 1, "action": "VALIDATED_DEMAND", "actor_id": 2,
>  "field_changed": "status", "old_value": "pending", "new_value": "validated",
>  "timestamp": "2026-08-11T10:00:00"}
> ```

- `DashboardStats`
  - Holds summary metrics for the dashboard.

> **Example.** Response of `GET /dashboard/me`:
> ```json
> {"user_id": 1, "total_invoices": 12, "pending_demands": 2,
>  "validated_demands": 5, "total_kwh": 12340}
> ```

What the file does overall:
- Ensures incoming and outgoing data is strongly validated.
- Protects the API from malformed payloads.
- Shapes the JSON responses returned to the frontend.

---

### [back/security.py](back/security.py)

This file handles authentication security.

Functions:

- `hash_password(plain)`
  - Converts a plain-text password into a bcrypt hash.
  - Used when creating or storing user passwords.

> **Example.**
> ```python
> from security import hash_password
> print(hash_password("secret123"))
> # -> "$2b$12$e9K...6y"   (a 60-character bcrypt string, always unique)
> ```

- `verify_password(plain, hashed)`
  - Compares a plain-text password with a stored hash.
  - Used during login.

> **Example.**
> ```python
> from security import hash_password, verify_password
> hashed = hash_password("secret123")
> verify_password("secret123", hashed)   # -> True
> verify_password("wrongpass", hashed)   # -> False
> ```

- `create_access_token(user_id, role)`
  - Generates a JWT containing the user ID and role.
  - Includes expiration information so tokens expire automatically.

> **Example.**
> ```python
> from security import create_access_token
> token = create_access_token(user_id=1, role="admin")
> print(token)  # -> "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwi..."
> ```
> The token expires after `settings.JWT_EXPIRE_MINUTES` (default 720 minutes = 12 hours).

- `decode_access_token(token)`
  - Validates a JWT.
  - Returns the decoded payload if the token is valid.
  - Returns nothing if the token is expired or invalid.

> **Example.**
> ```python
> from security import create_access_token, decode_access_token
> token = create_access_token(user_id=1, role="user")
> print(decode_access_token(token))
> # -> {"sub": "1", "role": "user", "iat": 1788900000, "exp": 1789332000}
> print(decode_access_token("garbage.token.here"))   # -> None
> ```

What the file does overall:
- Secures user accounts.
- Implements stateless authentication for the API.

---

### [back/services.py](back/services.py)

This file contains shared helper functions used by multiple routers.

Functions:

- `_check_extension(filename)`
  - Validates the uploaded file extension.
  - Rejects unsupported file types.
  - Ensures only allowed invoice formats are stored.

> **Example.**
> ```python
> from services import _check_extension
> _check_extension("facture.pdf")      # OK, no error
> _check_extension("facture.exe")      # raises HTTPException(400)
> # {"detail": "Unsupported file type '.exe'. Allowed: .jpeg, .jpg, .pdf, .png, .webp"}
> ```

- `save_upload_file(upload)`
  - Accepts an uploaded file.
  - Validates extension and size.
  - Saves the file into the uploads folder.
  - Generates a unique file name.
  - Returns the relative path of the stored file for database persistence.

> **Example.** Inside `POST /invoices/upload`:
> ```python
> path = save_upload_file(file)
> # e.g. -> "uploads/a3f9c1e2d4b6...pdf"  (uuid-based name, stored under back/uploads/)
> # If the file is over 10 MB it raises HTTPException(413):
> # {"detail": "File exceeds the 10 MB limit"}
> ```

- `create_audit_log(...)`
  - Creates an audit-log record linked to a demand.
  - Stores the actor, action, changed field, old value, and new value.
  - The `timestamp` is set to **local server time** via `datetime.now()`.

> **Example.** Used in the admin review endpoint:
> ```python
> entry = create_audit_log(
>     db,
>     demand=demand,
>     actor_id=admin.user_id,
>     action="VALIDATED_DEMAND",
>     field_changed="status",
>     old_value="pending",
>     new_value="validated",
> )
> db.commit()   # the entry is only persisted when the transaction commits
> ```

What the file does overall:
- Encapsulates file upload logic.
- Centralizes audit-trail creation.

---

### [back/seed.py](back/seed.py)

This file populates the database with demo data for testing the application.

Functions:

- `_get_or_create_user(db, name, email, role)`
  - Checks whether a user already exists by email.
  - Creates the user if necessary (password `demo123`, `account_status="active"`).
  - **On subsequent runs, re-activates demo accounts**: if `account_status` is not `"active"` or the role differs, it resets `account_status = "active"` and reapplies the role. This ensures demo accounts remain usable even after the backfill migration defaulted them to `pending`.

> **Example.**
> ```python
> user = _get_or_create_user(db, "Sami Rejeb", "sami.rejeb@steg.tn", "user")
> # First call -> creates the user with password "demo123", account_status "active".
> # Second call -> returns existing user; if account_status was "pending", sets it back to "active".
> ```

- `seed(db)`
  - Creates demo users (regular user + admin).
  - Adds 3 sample invoices with their demands (1 pending, 2 validated) plus audit logs **only on first run** (when the demo user has zero invoices).
  - Sample invoice files are referenced at `uploads/sample/steg_<invoice_no>.pdf`.

> **Example.** When `STEG_SEED=1` (default), running the app creates:
> - User `sami.rejeb@steg.tn` (password `demo123`)
> - Admin `admin.validation@steg.tn` (password `demo123`)
> - 3 sample invoices with their demands (1 pending, 2 validated), plus audit logs
>
> You can log in with either account:
> ```bash
> curl -X POST http://127.0.0.1:8000/auth/login \
>   -H "Content-Type: application/json" \
>   -d '{"email": "admin.validation@steg.tn", "password": "demo123"}'
> ```
> Seeding is idempotent — it only adds invoices the first time the demo user has none.

What the file does overall:
- Provides realistic sample data.
- Allows the application to be shown quickly in a demo environment.
- Keeps demo accounts active across restarts/migrations.

---

### [back/run.py](back/run.py)

This is a simple startup script for launching the backend.

What it does:
- Adds the backend directory to Python’s import path.
- Imports the application settings.
- Starts Uvicorn with the FastAPI app.

> **Example.**
> ```bash
> cd back
> python run.py
> # INFO:     Uvicorn running on http://127.0.0.1:8000
> ```
> Equivalent to: `uvicorn main:app --host 127.0.0.1 --port 8000`

---

## 4. Router-by-router explanation

### [back/routers/auth.py](back/routers/auth.py)

Functions:

- `_auth_response(user)`
  - Builds a JWT and wraps the user in an authentication response.

> **Example.**
> ```python
> _auth_response(user, access_token=create_access_token(user.user_id, user.role))
> # -> AuthResponse(access_token="eyJ...", token_type="bearer", user=UserOut(...))
> ```

- `register(payload, db)`
  - Creates a new user account.
  - Checks whether the email already exists.
  - Hashes the password.
  - Saves the user with `created_at` set to **local server time** (`datetime.now()`).
  - Returns a JWT and the user profile.

> **Example.** `POST /auth/register` (201 Created)
> ```bash
> curl -X POST http://127.0.0.1:8000/auth/register \
>   -H "Content-Type: application/json" \
>   -d '{"full_name": "Amina Ben Ali", "email": "amina@steg.tn", "password": "secret123"}'
> ```
> ```json
> {"access_token": "eyJ...", "token_type": "bearer",
>  "user": {"user_id": 1, "full_name": "Amina Ben Ali", "email": "amina@steg.tn",
>           "role": "user", "account_status": "pending", "created_at": "2026-08-11T09:00:00"}}
> ```
> Duplicate email -> 409:
> ```json
> {"detail": "An account with this email already exists"}
> ```

- `login(payload, db)`
  - Authenticates the user with email and password.
  - Verifies the stored password hash.
  - Returns a JWT if the credentials are correct **and** the account is active.
  - Rejects pending accounts with a distinct 403 message asking the user to wait for admin approval.
  - Rejects inactive (banned/deactivated) accounts with a distinct 403 message telling them to contact an administrator.

> **Example.** `POST /auth/login`
> ```bash
> curl -X POST http://127.0.0.1:8000/auth/login \
>   -H "Content-Type: application/json" \
>   -d '{"email": "amina@steg.tn", "password": "secret123"}'
> ```
> Wrong credentials -> 401:
> ```json
> {"detail": "Invalid email or password"}
> ```
> Correct credentials but account **pending** -> 403:
> ```json
> {"detail": "Your account is awaiting admin approval. Please try again once it is verified."}
> ```
> Correct credentials but account **inactive** -> 403:
> ```json
> {"detail": "Your account has been deactivated. Contact an administrator."}
> ```

- `update_me(payload, current_user)` (route `PATCH /auth/me`)
  - Updates the authenticated user's full name.

> **Example.** `PATCH /auth/me`
> ```bash
> curl -X PATCH http://127.0.0.1:8000/auth/me \
>   -H "Authorization: Bearer <JWT>" \
>   -H "Content-Type: application/json" \
>   -d '{"full_name": "Amina B."}'
> ```
> ```json
> {"user_id": 1, "full_name": "Amina B.", "email": "amina@steg.tn",
>  "role": "user", "account_status": "pending", "created_at": "2026-08-11T09:00:00"}
> ```

- `me(current_user)`
  - Returns the authenticated user profile.
  - Useful for frontend pages that need the logged-in user details.

> **Example.** `GET /auth/me` (requires `Authorization: Bearer <JWT>`)
> ```json
> {"user_id": 1, "full_name": "Amina Ben Ali", "email": "amina@steg.tn",
>  "role": "user", "account_status": "pending", "created_at": "2026-08-11T09:00:00"}
> ```

---

### [back/routers/invoices.py](back/routers/invoices.py)

Functions:

- `_invoice_out(invoice)`
  - Converts an ORM invoice to the response schema.
  - Also attaches the demand information if the invoice is linked to one.

> **Example.**
> ```python
> out = _invoice_out(invoice)
> print(out.demand_id)      # -> 1 (or None if no demand exists)
> print(out.demand_status)  # -> "pending" (or None)
> ```

- `_own_invoice_or_404(db, invoice_id, user)`
  - Finds an invoice by ID.
  - Ensures the invoice belongs to the current user or the requester is an admin.
  - Raises 404 or 403 errors when access is not allowed.

> **Example.**
> ```python
> invoice = _own_invoice_or_404(db, 99, current_user)
> # unknown id        -> 404 {"detail": "Invoice not found"}
> # not yours (user)  -> 403 {"detail": "Not your invoice"}
> # admin             -> allowed even for other users' invoices
> ```

- `upload_invoice(file, db, current_user)`
  - Saves the uploaded invoice file.
  - Creates an invoice record in the database with `uploaded_at` set to **local server time** (`datetime.now()`).
  - Marks the initial status as uploaded.

> **Example.** `POST /invoices/upload` (multipart, 201 Created)
> ```bash
> curl -X POST http://127.0.0.1:8000/invoices/upload \
>   -H "Authorization: Bearer <JWT>" \
>   -F "file=@facture.pdf"
> ```
> ```json
> {"invoice": {"invoice_id": 1, "user_id": 1, "file_name": "facture.pdf",
>              "supplier": "STEG", "status": "uploaded", "...": "..."},
>  "message": "Upload successful. Awaiting value validation."}
> ```

- `list_my_invoices(db, current_user)`
  - Returns all invoices belonging to the authenticated user.
  - Orders them from newest to oldest.

> **Example.** `GET /invoices/mine`
> ```json
> {"invoices": [{"invoice_id": 2, "status": "pending", "...": "..."},
>               {"invoice_id": 1, "status": "uploaded", "...": "..."}],
>  "total": 2}
> ```

- `get_invoice(invoice_id, db, current_user)`
  - Retrieves one specific invoice.
  - Restricts access to the invoice owner or admin.

> **Example.** `GET /invoices/1`
> ```json
> {"invoice_id": 1, "user_id": 1, "file_name": "facture.pdf", "supplier": "STEG",
>  "status": "uploaded", "demand_id": null, "demand_status": null, "...": "..."}
> ```

- `update_invoice_values(invoice_id, payload, db, current_user)`
  - Updates the confirmed invoice fields entered by the user.
  - Marks the invoice as validated_by_user.

> **Example.** `PUT /invoices/1/values`
> ```bash
> curl -X PUT http://127.0.0.1:8000/invoices/1/values \
>   -H "Authorization: Bearer <JWT>" \
>   -H "Content-Type: application/json" \
>   -d '{"supplier": "STEG", "invoice_no": "2026-STEG-77491", "kwh_consumed": 1230, "...": "..."}'
> ```
> Response now shows `"status": "validated_by_user"`.

---

### [back/routers/demands.py](back/routers/demands.py)

Functions:

- `_my_demand_out(demand)`
  - Converts a demand and its linked invoice into a user-friendly response object.

> **Example.**
> ```python
> _my_demand_out(demand)
> # -> MyDemandOut(demand_id=1, invoice_id=1, invoice_no="2026-STEG-77491",
> #                supplier="STEG", amount_incl_tax=384.45, status="pending", ...)
> ```

- `submit_demand(payload, db, current_user)`
  - Validates that the invoice exists and belongs to the current user.
  - Ensures the invoice has already been user-validated.
  - Prevents duplicate demands for the same invoice.
  - Creates a new demand with `submitted_at` set to **local server time** (`datetime.now()`) and updates the invoice status to pending.

> **Example.** `POST /demands` (201 Created)
> ```bash
> curl -X POST http://127.0.0.1:8000/demands \
>   -H "Authorization: Bearer <JWT>" \
>   -H "Content-Type: application/json" \
>   -d '{"invoice_id": 1}'
> ```
> ```json
> {"demand_id": 1, "invoice_id": 1, "user_id": 1, "status": "pending",
>  "submitted_at": "2026-08-11T09:30:00", "reviewed_by_admin_id": null, "reviewed_at": null}
> ```
> Guard errors:
> - Invoice not user-validated -> 400 `"Invoice must be user-validated before a demand can be submitted"`
> - Demand already exists -> 409 `"A demand already exists for this invoice"`

- `list_my_demands(db, current_user)`
  - Returns all demands submitted by the current user.
  - Orders them from newest to oldest.

> **Example.** `GET /demands/mine`
> ```json
> [{"demand_id": 1, "invoice_id": 1, "invoice_no": "2026-STEG-77491",
>   "supplier": "STEG", "amount_incl_tax": 384.45, "status": "pending",
>   "submitted_at": "2026-08-11T09:30:00"}]
> ```

---

### [back/routers/admin.py](back/routers/admin.py)

Functions:

- `_admin_demand_out(demand)`
  - Builds the admin-facing demand response object.
  - Includes the requester’s name and email.

> **Example.**
> ```python
> _admin_demand_out(demand)
> # -> AdminDemandOut(..., user_id=1, user_name="Amina Ben Ali", user_email="amina@steg.tn")
> ```

- `admin_list_demands(db, admin, status_filter)`
  - Lists all demands across all users for admin review.
  - Supports filtering by demand status.
  - Validates the requested status value.

> **Example.** `GET /admin/demands?status=pending`
> ```json
> [{"demand_id": 1, "invoice_id": 1, "invoice_no": "2026-STEG-77491",
>   "supplier": "STEG", "amount_incl_tax": 384.45, "status": "pending",
>   "submitted_at": "2026-08-11T09:30:00",
>   "user_id": 1, "user_name": "Amina Ben Ali", "user_email": "amina@steg.tn"}]
> ```
> Invalid filter -> 400:
> ```json
> {"detail": "status must be one of: all, pending, rejected, validated"}
> ```

- `admin_review_demand(demand_id, decision, db, admin)`
  - Lets an admin approve or reject a demand.
  - Updates the demand status.
  - Updates the invoice status.
  - Writes an audit log entry.
  - Records who reviewed it and when (`reviewed_at` stored in **local server time** via `datetime.now()`).

> **Example.** `PATCH /admin/demands/1`
> ```bash
> curl -X PATCH http://127.0.0.1:8000/admin/demands/1 \
>   -H "Authorization: Bearer <ADMIN_JWT>" \
>   -H "Content-Type: application/json" \
>   -d '{"status": "validated"}'
> ```
> ```json
> {"demand_id": 1, "invoice_id": 1, "invoice_no": "2026-STEG-77491",
>  "supplier": "STEG", "amount_incl_tax": 384.45, "status": "validated",
>  "submitted_at": "2026-08-11T09:30:00",
>  "user_id": 1, "user_name": "Amina Ben Ali", "user_email": "amina@steg.tn"}
> ```
> An audit log row is also inserted (action `VALIDATED_DEMAND` or `REJECTED_DEMAND`).
> Re-reviewing an already-reviewed demand -> 409 `"Demand already reviewed (status=validated)"`.

- `admin_audit_logs(db, admin)`
  - Returns the full list of audit log entries.
  - Useful for reviewing the workflow history.

> **Example.** `GET /admin/audit`
> ```json
> [{"audit_id": 1, "demand_id": 1, "action": "VALIDATED_DEMAND", "actor_id": 2,
>   "field_changed": "status", "old_value": "pending", "new_value": "validated",
>   "timestamp": "2026-08-11T10:00:00"}]
> ```

Additional admin endpoints (user and invoice management):

- `GET /admin/users` — list all **non-admin users** (newest first). Administrator accounts are intentionally excluded (`WHERE role = 'user'`) so they cannot be acted upon from this view.
- `POST /admin/users` — create a user with `created_at` set to **local server time**; body uses `AdminUserCreate`, e.g.:
  ```json
  {"full_name": "Khalil Trabelsi", "email": "khalil@steg.tn",
   "role": "user", "account_status": "active", "password": "secret123"}
  ```
- `PATCH /admin/users/{user_id}` — update a user's name, email, role, `account_status`, or password.
  - **Guards:** Returns `400 "Administrator accounts cannot be modified"` if the target user has `role = "admin"`.
  - **Guard:** Returns `400 "You cannot edit your own account here"` if `user_id == admin.user_id`.
  - Typical admin action: set `account_status` to `"active"` (approve) or `"inactive"` (ban/deactivate).
- `DELETE /admin/users/{user_id}` — delete a user (returns 204 No Content).
  - **Guards:** Returns `400 "Administrator accounts cannot be deleted"` if the target user has `role = "admin"`.
  - **Guard:** Returns `400 "You cannot delete your own account"` if `user_id == admin.user_id`.
- `GET /admin/invoices` — list all invoices with owner name/email and demand info.
- `POST /admin/invoices` — create an invoice with `uploaded_at` set to **local server time**; body uses `AdminInvoiceCreate`.
- `PATCH /admin/invoices/{invoice_id}` — update an invoice.
- `DELETE /admin/invoices/{invoice_id}` — delete an invoice (204 No Content).

---

### [back/routers/dashboard.py](back/routers/dashboard.py)

Functions:

- `_stats_for(db, user_id)`
  - Computes dashboard metrics for a specific user.
  - Counts invoices, pending demands, validated demands, and total kwh consumed.

> **Example.**
> ```python
> stats = _stats_for(db, user_id=1)
> # -> DashboardStats(user_id=1, total_invoices=12, pending_demands=2,
> #                   validated_demands=5, total_kwh=12340)
> ```

- `my_dashboard_stats(db, current_user)`
  - Returns the dashboard summary for the signed-in user.

> **Example.** `GET /dashboard/me`
> ```json
> {"user_id": 1, "total_invoices": 12, "pending_demands": 2,
>  "validated_demands": 5, "total_kwh": 12340}
> ```

- `admin_user_dashboard_stats(user_id, db, admin)`
  - Returns the same dashboard summary for any specific user, but only for admins.

> **Example.** `GET /admin/dashboard/1` (admin only)
> ```json
> {"user_id": 1, "total_invoices": 12, "pending_demands": 2,
>  "validated_demands": 5, "total_kwh": 12340}
> ```
> Unknown user -> 404 `{"detail": "User not found"}`.

---

## 5. Typical backend flow

A common flow in this app is:
1. User registers or logs in.
2. User uploads an invoice.
3. User validates the extracted invoice values.
4. User submits a demand for the invoice.
5. Admin reviews the demand.
6. The invoice and demand statuses are updated.
7. Audit logs record the decision.

> **Example.** End-to-end sequence of HTTP calls:
> ```bash
> # 1. Login and capture the JWT
> TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login \
>   -H "Content-Type: application/json" \
>   -d '{"email":"admin.validation@steg.tn","password":"demo123"}' | jq -r .access_token)
>
> # 2. Upload a facture
> curl -X POST http://127.0.0.1:8000/invoices/upload \
>   -H "Authorization: Bearer $TOKEN" -F "file=@facture.pdf"
>
> # 3. Confirm the OCR values
> curl -X PUT http://127.0.0.1:8000/invoices/1/values \
>   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
>   -d '{"supplier":"STEG","invoice_no":"2026-STEG-77491","amount_incl_tax":384.45,
>        "currency":"TND","kwh_consumed":1230}'
>
> # 4. Submit a demand
> curl -X POST http://127.0.0.1:8000/demands \
>   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
>   -d '{"invoice_id":1}'
>
> # 5-7. Admin approves; statuses update and an audit log is written
> curl -X PATCH http://127.0.0.1:8000/admin/demands/1 \
>   -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
>   -d '{"status":"validated"}'
> curl http://127.0.0.1:8000/admin/audit -H "Authorization: Bearer $ADMIN_TOKEN"
> ```

---

## 6. Short summary

- Authentication is handled by [back/security.py](back/security.py) and [back/deps.py](back/deps.py).
- Database structure is defined in [back/models.py](back/models.py).
- API routes are split into router files under [back/routers](back/routers).
- File upload and audit logic live in [back/services.py](back/services.py).
- Application settings live in [back/config.py](back/config.py).

If you want, I can also turn this into a more visual architecture diagram or a shorter developer cheat sheet.
