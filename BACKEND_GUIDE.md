# Backend Architecture & Functional Guide

This document provides a comprehensive, deep-dive reference for the STEG InvoiceFlow FastAPI backend. It details the purpose of each file, the exact function signatures, **what activates/triggers each function**, **why specific methods/patterns were chosen**, and **concrete usage examples**.

---

## 1. Core Architecture & Stack Rationale

The backend is built as a high-performance REST API connected to an enterprise SQL Server database (via LocalDB `MSSQLLocalDB` or standalone SQL Server instances).

### Technology Selection Rationale:
- **FastAPI**: Chosen over Flask/Django for high-performance asynchronous request handling, automatic OpenAPI schema generation, strict type safety via Python type annotations, and built-in dependency injection (`Depends`).
- **SQLAlchemy ORM (v2.0)**: Selected to decouple database logic from raw SQL string manipulations while maintaining full support for enterprise SQL Server features (ODBC connectivity, transactions, foreign key cascades).
- **Pydantic (v2.0)**: Used for strong request payload parsing and response serialization, guaranteeing that incoming JSON payload structures strictly conform to application domain models.
- **PyJWT & Bcrypt**: Implemented for stateless, scalable authentication. Passwords are hashed using salted bcrypt key derivation (`bcrypt.gensalt()`), and user sessions are managed statelessly via signed JWT bearer tokens (`HS256`).
- **PyTesseract & Poppler-utils**: Integrated for document OCR preprocessing and text recognition, extracting billing figures directly from digital and scanned PDF/image invoices.

---

## 2. Backend Folder & File Structure

```
back/
├── config.py           # Central configuration & environment variables
├── database.py         # DB engine setup, session management & schema migrations
├── deps.py             # Auth & Role-Based Access Control (RBAC) dependencies
├── main.py             # FastAPI entry point, lifespan hooks & static routing
├── models.py           # SQLAlchemy ORM database models
├── ocr_service.py      # Tesseract OCR extraction engine & regex parser
├── requirements.txt    # Python package dependencies
├── run.py              # Application startup script
├── schemas.py          # Pydantic request/response validation schemas
├── security.py         # Bcrypt password hashing & JWT token handling
├── seed.py             # Idempotent seed script for demo accounts & invoices
├── services.py         # Shared file storage & audit logging helper services
└── routers/
    ├── admin.py        # Admin review queue, user management & audit logs
    ├── auth.py         # User registration, login & profile endpoints
    ├── dashboard.py    # User dashboard statistics & analytical aggregations
    ├── demands.py      # Invoice demand creation & submission endpoints
    └── invoices.py     # Invoice upload, OCR triggering & value persistence
```

---

## 3. Comprehensive File-by-File & Function-by-Function Reference

---

### 3.1 `back/main.py`

**File Overview**:
Serves as the root entry point for the FastAPI server. It initializes the app instance, registers CORS middleware, configures static asset serving (frontend and upload storage), handles application lifecycle hooks (startup/shutdown), and mounts router endpoints.

---

#### Function: `lifespan(_app: FastAPI)`
- **What it does**: Context manager executed during app startup and shutdown. On startup, it triggers `init_db()` to ensure the database schema exists and applies additive migrations. If `settings.SEED` is enabled, it automatically seeds default demo accounts.
- **Activation Trigger**: Triggered automatically by the FastAPI framework when the Uvicorn/Gunicorn server boots up.
- **Why this method?**: Replaces deprecated `@app.on_event("startup")` event handlers with FastAPI's modern lifespan context manager pattern, guaranteeing proper resource cleanup upon shutdown.
- **Example**:
  ```python
  # Activated automatically on server launch:
  # uvicorn main:app --reload
  ```

---

#### Function: `health()`
- **What it does**: Returns an HTTP status object verifying server health, service name, and API version.
- **Activation Trigger**: Triggered by HTTP `GET /health` requests from load balancers, health checkers, or frontend connection tests.
- **Why this method?**: Standard lightweight health endpoint that requires zero database queries, enabling instant status checks.
- **Example**:
  ```bash
  curl -X GET http://127.0.0.1:8000/health
  ```
  ```json
  {"status": "ok", "service": "steg-backend", "version": "1.0.0"}
  ```

---

#### Function: `index()`
- **What it does**: Serves the primary `index.html` single-page application file to client browsers.
- **Activation Trigger**: Triggered by HTTP `GET /` requests when a user navigates to the root URL.
- **Why this method?**: Allows FastAPI to serve the SPA directly without requiring an external reverse proxy (like Nginx) in standalone development environments.
- **Example**:
  ```bash
  curl -X GET http://127.0.0.1:8000/
  ```

---

### 3.2 `back/config.py`

**File Overview**:
Contains application configuration, environment variable parsing, upload constraints, role definitions, and dynamic SQL Server connection string generators.

---

#### Function: `_detect_db_server()`
- **What it does**: Inspects the environment variable `STEG_DB_SERVER`. If absent, defaults to Windows LocalDB instance `(localdb)\MSSQLLocalDB`.
- **Activation Trigger**: Executed during module loading when `Settings` class is instantiated.
- **Why this method?**: Ensures zero-configuration local development out of the box on Windows while supporting override in production via environment variables.

---

#### Class: `Settings`
- **What it contains**:
  - `DB_SERVER`, `DB_NAME`, `DB_DRIVER`: Connection parameters for SQL Server PyODBC driver.
  - `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`: Secret key and expiry window (default 720 minutes / 12 hours) for JWT tokens.
  - `MAX_UPLOAD_MB`, `ALLOWED_UPLOAD_EXTENSIONS`: File validation constraints (`10 MB`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`).
  - `INVOICE_STATUSES`, `DEMAND_STATUSES`: Allowed workflow state sets (`pending`, `approved`, `validated`, `rejected`, `uploaded`).
- **Properties**:
  - `_odbc_connect(database)`: Formats standard ODBC connection string with trusted authentication (`Trusted_Connection=yes; TrustServerCertificate=yes`).
  - `database_url`: URL-encodes the ODBC string for SQLAlchemy engine compatibility using `mssql+pyodbc:///?odbc_connect=...`.
  - `master_url`: Generates connection URL targeting SQL Server's `master` DB to check/create the target application DB dynamically.
- **Why this method?**: Encapsulating configuration in a single class prevents scattering magic constants across the codebase and centralizes security settings.
- **Example**:
  ```python
  from config import settings
  print(settings.database_url)
  ```

---

### 3.3 `back/database.py`

**File Overview**:
Manages SQLAlchemy engine creation, DB session creation (`SessionLocal`), initial database creation on SQL Server, and automatic schema migrations.

---

#### Variable: `engine` & `SessionLocal`
- **What it does**: `engine` holds the connection pool to SQL Server (`pool_pre_ping=True`, `pool_recycle=1800`). `SessionLocal` is the sessionmaker factory bound to `engine`.
- **Why this method?**: `pool_pre_ping=True` prevents "stale connection" errors when SQL Server drops idle connections. `pool_recycle=1800` recycles connections every 30 minutes.

---

#### Function: `get_db()`
- **What it does**: Generator function yielding an active database session (`Session`) and guaranteeing closing of the session in a `finally` block when the request finishes.
- **Activation Trigger**: Injected into FastAPI route handlers via `Depends(get_db)`.
- **Why this method?**: Ensures clean session lifecycle management, preventing connection leaks and hanging locks in SQL Server.
- **Example**:
  ```python
  @router.get("/items")
  def get_items(db: Session = Depends(get_db)):
      return db.query(Item).all()
  ```

---

#### Function: `_ensure_database_exists()`
- **What it does**: Connects to SQL Server `master` database and executes `IF DB_ID('StegDB') IS NULL CREATE DATABASE [StegDB]`.
- **Activation Trigger**: Invoked by `init_db()` during application lifespan startup.
- **Why this method?**: Eliminates manual database creation steps in SSMS; the backend auto-creates `StegDB` on first run.

---

#### Function: `run_migrations()`
- **What it does**: Executes idempotent raw DDL/DML statements to alter existing tables (adding missing columns like `kwh_consumed`, `due_date`, `account_status`), updating legacy records, and switching timestamp default constraints from UTC to local server time (`DEFAULT (getdate())`).
- **Activation Trigger**: Invoked by `init_db()` during startup.
- **Why this method?**: Allows lightweight schema evolution without introducing complex migration frameworks (like Alembic) for straightforward application requirements.

---

#### Function: `init_db()`
- **What it does**: Coordinates the entire DB setup pipeline: creates upload directories, ensures target DB exists, issues `Base.metadata.create_all(bind=engine)` to create tables, and runs migrations.
- **Activation Trigger**: Invoked by `lifespan` context manager in `main.py` on startup.

---

### 3.4 `back/deps.py`

**File Overview**:
Contains security dependencies for authenticating incoming API requests and enforcing Role-Based Access Control (RBAC).

---

#### Function: `get_current_user(db: Session, token: str)`
- **What it does**: Extracts the HTTP `Authorization: Bearer <token>` header, decodes the JWT via `decode_access_token()`, extracts `user_id`, queries the `Users` table, and returns the authenticated `User` model object.
- **Activation Trigger**: Injected as a dependency into protected user endpoints (e.g. `/invoices/mine`, `/demands`).
- **Error Conditions**: Throws `HTTP 401 Unauthorized` if token is missing, expired, invalid, or user does not exist in DB.
- **Why this method?**: Centralizes authentication logic so individual endpoints do not duplicate JWT parsing code.
- **Example**:
  ```python
  @router.get("/me")
  def me(current_user: User = Depends(get_current_user)):
      return current_user
  ```

---

#### Function: `require_admin(current_user: User)`
- **What it does**: Inspects `current_user.role`. If `current_user.role != "admin"`, raises `HTTP 403 Forbidden`. Returns `current_user` if role is `"admin"`.
- **Activation Trigger**: Injected as a dependency into all admin review queue endpoints in `back/routers/admin.py`.
- **Why this method?**: Guarantees strict server-side authorization enforcement, ensuring normal users can never execute admin actions even if they bypass frontend UI checks.
- **Example**:
  ```python
  @router.get("/admin/users")
  def list_users(admin: User = Depends(require_admin)):
      ...
  ```

---

### 3.5 `back/security.py`

**File Overview**:
Contains cryptographic routines for password hashing and stateless JWT token issuance/validation.

---

#### Function: `hash_password(plain: str) -> str`
- **What it does**: Hashes a plain-text password using `bcrypt.hashpw()` with a random salt (`bcrypt.gensalt()`). Returns a string.
- **Activation Trigger**: Invoked during user registration (`POST /auth/register`) or admin user creation/update (`POST /admin/users`).
- **Why this method?**: Bcrypt is a secure, computationally expensive key derivation function resistant to rainbow table and brute-force attacks.

---

#### Function: `verify_password(plain: str, hashed: str) -> bool`
- **What it does**: Compares a candidate plain-text password against a stored bcrypt hash using `bcrypt.checkpw()`. Returns `True` if match, `False` otherwise.
- **Activation Trigger**: Invoked during user authentication (`POST /auth/login`).
- **Why this method?**: Safely handles constant-time string comparison, protecting against timing attack vulnerabilities.

---

#### Function: `create_access_token(user_id: int, role: str) -> str`
- **What it does**: Builds a JWT payload containing claims: `sub` (user_id), `role`, `iat` (issued at time), `exp` (expiration time), and encodes it using `jwt.encode()` with `settings.JWT_SECRET` and algorithm `HS256`.
- **Activation Trigger**: Invoked upon successful login or registration in `auth.py`.
- **Why this method?**: Stateless JWT tokens eliminate the need for server-side session lookup tables in DB, enabling scalable horizontal scaling.

---

#### Function: `decode_access_token(token: str) -> dict | None`
- **What it does**: Decodes and verifies the signature and expiration of a JWT token string using `jwt.decode()`. Returns payload dictionary or `None` if invalid/expired.
- **Activation Trigger**: Invoked by `get_current_user` in `deps.py` on protected HTTP requests.

---

### 3.6 `back/models.py`

**File Overview**:
Defines SQLAlchemy ORM mapped entities corresponding to database tables: `Users`, `Invoices`, `Demands`, `AuditLogs`.

---

#### Class: `User(Base)`
- **Table Name**: `Users`
- **Columns**: `user_id` (PK), `full_name`, `email` (Unique Index), `password_hash`, `role` (`user` | `admin`), `account_status` (`active` | `pending` | `inactive`), `created_at`.
- **Relationships**: `invoices` (one-to-many with `Invoice`, cascade delete), `demands` (one-to-many with `Demand`).

#### Class: `Invoice(Base)`
- **Table Name**: `Invoices`
- **Columns**: `invoice_id` (PK), `user_id` (FK -> `Users.user_id`), `file_path`, `supplier`, `invoice_no`, `invoice_date`, `amount_excl_tax`, `tva`, `amount_incl_tax`, `currency`, `kwh_consumed`, `due_date`, `status`, `uploaded_at`.
- **Property `file_name`**: Computes basename from `file_path` (e.g. `uploads/abc.pdf` -> `abc.pdf`).
- **Relationships**: `owner` (many-to-one with `User`), `demand` (one-to-one with `Demand`, cascade delete).

#### Class: `Demand(Base)`
- **Table Name**: `Demands`
- **Columns**: `demand_id` (PK), `invoice_id` (FK -> `Invoices.invoice_id`, Unique), `user_id` (FK -> `Users.user_id`), `status` (`pending` | `approved` | `rejected`), `submitted_at`, `reviewed_by_admin_id` (FK -> `Users.user_id`), `reviewed_at`.
- **Relationships**: `invoice` (one-to-one with `Invoice`), `requester` (many-to-one with `User`), `reviewer` (many-to-one with `User`), `audit_logs` (one-to-many with `AuditLog`, cascade delete).

#### Class: `AuditLog(Base)`
- **Table Name**: `AuditLogs`
- **Columns**: `audit_id` (PK), `demand_id` (FK -> `Demands.demand_id`), `actor_id` (FK -> `Users.user_id`), `action`, `field_changed`, `old_value`, `new_value`, `timestamp`.

---

### 3.7 `back/schemas.py`

**File Overview**:
Defines Pydantic request and response models used for input validation, sanitization, and JSON response serialization.

---

#### Key Pydantic Models & Field Validators:
- **`RegisterRequest`**: Validates user registration. Uses `@field_validator("full_name")` to trim whitespace. Ensures password length >= 6.
- **`LoginRequest`**: Validates login credentials (`email`, `password`).
- **`UserOut`**: Wire response schema for user identity (`user_id`, `full_name`, `email`, `role`, `account_status`, `created_at`). Configured with `from_attributes = True`.
- **`AuthResponse`**: Response containing `access_token`, `token_type = "bearer"`, and nested `user: UserOut`.
- **`InvoiceValuesUpdate`**: Payload submitted when user confirms extracted OCR values (`supplier`, `invoice_no`, `invoice_date`, `amount_excl_tax`, `tva`, `amount_incl_tax`, `currency`, `kwh_consumed`, `due_date`).
- **`InvoiceOut`**: Complete wire output format for an invoice merged with its associated `demand_id` and `demand_status`.
- **`DemandDecision`**: Payload for admin review decision (`status: Field(pattern="^(approved|validated|rejected)$")`).
- **`DashboardStats`**: Aggregated statistics summary (`total_invoices`, `pending_demands`, `validated_demands`, `total_kwh`).

---

### 3.8 `back/services.py`

**File Overview**:
Contains application service helpers for file upload persistence and audit trail logging.

---

#### Function: `_check_extension(filename: str)`
- **What it does**: Checks if file extension belongs to `settings.ALLOWED_UPLOAD_EXTENSIONS`. Raises `HTTP 400 Bad Request` if invalid.
- **Activation Trigger**: Called inside `save_upload_file()`.

---

#### Function: `save_upload_file(upload: UploadFile) -> str`
- **What it does**: Validates extension, streams uploaded bytes in 1 MB chunks (`SAVE_CHUNK_SIZE`), enforces max file size limit (`settings.MAX_UPLOAD_MB`), generates a secure unique filename using `uuid.uuid4().hex`, saves file into `uploads/` directory, and returns store-relative path.
- **Activation Trigger**: Called by `upload_invoice()` in `routers/invoices.py` during HTTP `POST /invoices/upload`.
- **Why this method?**: Streaming file chunks prevents RAM exhaustion when uploading large documents. Unlinking partial files on failure prevents orphan file accumulation.
- **Example**:
  ```python
  saved_path = save_upload_file(uploaded_file)
  # returns "uploads/e3a89078f4a1.pdf"
  ```

---

#### Function: `create_audit_log(db, demand, actor_id, action, field_changed, old_value, new_value)`
- **What it does**: Instantiates a new `AuditLog` ORM model record and adds it to the DB session.
- **Activation Trigger**: Called when a demand is created/updated or when an admin reviews a demand in `routers/invoices.py`, `routers/demands.py`, and `routers/admin.py`.
- **Why this method?**: Centralizes audit logging to guarantee consistency across all system state transitions.

---

### 3.9 `back/ocr_service.py`

**File Overview**:
Implements optical character recognition (OCR) and PDF parsing pipelines using PyTesseract, Poppler (`pdf2image`), and regular expressions tailored for STÈG utility invoices.

---

#### Function: `run_ocr(file_path: str) -> dict`
- **What it does**:
  1. Checks if input file is PDF or image. If PDF, converts first page to image using `pdf2image.convert_from_path()`.
  2. Runs Tesseract OCR engine (`pytesseract.image_to_string()`) with French/Arabic language support.
  3. Applies specialized regular expressions to parse STÈG fields:
     - `facture`: Regex search for invoice number (e.g. `2026-STEG-77491`).
     - `date`: Billing date string extraction.
     - `montant_ht`, `total_3_taxes`, `montant_ttc`: Financial amounts parsed into floats.
  4. Returns dictionary containing raw OCR output, parsed fields, confidence metric, and mapped values ready for database insertion.
- **Activation Trigger**: Called inside `upload_invoice()` in `routers/invoices.py` immediately after an invoice file is saved.
- **Why this method?**: Auto-parsing fields reduces manual data entry effort for users while allowing them to review and edit extracted figures before final submission.

---

### 3.10 `back/seed.py`

**File Overview**:
Seeds demo accounts and sample STÈG invoices idempotently on initial application setup.

---

#### Function: `_get_or_create_user(db, name, email, role) -> User`
- **What it does**: Queries user by email. If missing, creates active user with default password `demo123`. If present, ensures status is active and role matches.

#### Function: `seed(db: Session)`
- **What it does**: Seeds demo accounts:
  - User: `sami.rejeb@steg.tn`
  - Admin: `admin.validation@steg.tn`
  Seeds 3 sample STÈG invoices (`2026-STEG-77491`, `2026-STEG-55120`, `2026-STEG-33910`) with corresponding demands (`pending`, `approved`) and audit logs if the user has 0 invoices.
- **Activation Trigger**: Called by app `lifespan` on startup if `settings.SEED` is enabled.

---

### 3.11 `back/run.py`

**File Overview**:
CLI startup utility executing `uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)`.

---

### 3.12 `back/routers/auth.py`

**File Overview**:
Contains API endpoints for user registration, authentication, session identity retrieval, and profile updates.

---

#### Endpoint: `POST /auth/register` (`register`)
- **What it does**: Registers a new user account. Hashes password using bcrypt. Defaults role to `user` and `account_status` to `active`. Returns JWT access token and user identity.
- **Activation Trigger**: Triggered by user filling registration form on frontend auth modal.
- **Example**:
  ```bash
  curl -X POST http://127.0.0.1:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"full_name": "New User", "email": "user@steg.tn", "password": "password123"}'
  ```

---

#### Endpoint: `POST /auth/login` (`login`)
- **What it does**: Validates email and bcrypt password. Checks account status (`account_status == 'active'`). Issues signed JWT token.
- **Activation Trigger**: Triggered by user signing in on frontend auth modal.

---

#### Endpoint: `GET /auth/me` (`get_me`)
- **What it does**: Returns identity profile of authenticated user.
- **Activation Trigger**: Triggered by frontend on page load (`restoreSession()`) to verify JWT session validity.

---

#### Endpoint: `PATCH /auth/me` (`update_me`)
- **What it does**: Allows authenticated user to update their full name.
- **Activation Trigger**: Triggered from account profile modal on frontend.

---

### 3.13 `back/routers/invoices.py`

**File Overview**:
Handles file upload, OCR extraction execution, invoice listing, inspection, value confirmation, and deletion.

---

#### Endpoint: `POST /invoices/upload` (`upload_invoice`)
- **What it does**: Saves uploaded PDF/image file, creates `Invoice` record in status `uploaded`, runs `run_ocr()`, auto-populates mapped OCR values, and returns `InvoiceUploadResponse` containing invoice details and OCR extraction output.
- **Activation Trigger**: Triggered when user selects/drops a file on frontend dropzone.

---

#### Endpoint: `GET /invoices/mine` (`list_my_invoices`)
- **What it does**: Queries all invoices owned by current user using `selectinload(Invoice.demand)`. Returns list sorted newest first.
- **Activation Trigger**: Triggered when dashboard loads user's invoice directory table.

---

#### Endpoint: `GET /invoices/{invoice_id}` (`get_invoice`)
- **What it does**: Fetches single invoice details. Enforces owner or admin access check (`_own_invoice_or_404`).
- **Activation Trigger**: Triggered when user/admin clicks "Inspect Invoice" button.

---

#### Endpoint: `PUT /invoices/{invoice_id}/values` (`update_invoice_values`)
- **What it does**: Persists confirmed extraction values submitted by user. **Crucial Workflow Logic**: Automatically creates or resets the associated `Demand` status to **`pending`** and sets `invoice.status = "pending"`, immediately pushing the invoice into the **Admin Review Queue**. Writes audit log entry `USER_MODIFIED_DEMAND`.
- **Activation Trigger**: Triggered when user clicks **Confirm & Save Validated Values** in OCR verification panel.
- **Why this method?**: Fulfills requirement 2 by eliminating manual intermediate steps: confirming extracted OCR figures automatically queues the demand for admin review.

---

#### Endpoint: `DELETE /invoices/{invoice_id}` (`delete_my_invoice`)
- **What it does**: Deletes an invoice owned by current user (cascade deletes linked demand and audit logs).
- **Activation Trigger**: Triggered when user clicks "Delete Facture" button.

---

### 3.14 `back/routers/demands.py`

**File Overview**:
Handles explicit demand creation and personal demand list management.

---

#### Endpoint: `POST /demands` (`submit_demand`)
- **What it does**: Submits or re-submits a demand for an invoice. Sets demand status and invoice status to `pending`, records submission timestamp, and logs audit event `USER_MODIFIED_DEMAND`.
- **Activation Trigger**: Triggered if user manually clicks "Submit Demand" button on an unsubmitted invoice.

---

#### Endpoint: `GET /demands/mine` (`list_my_demands`)
- **What it does**: Returns all demands belonging to authenticated user, sorted newest first.
- **Activation Trigger**: Triggered when user views personal demands summary.

---

#### Endpoint: `DELETE /demands/{demand_id}` (`delete_my_demand`)
- **What it does**: Deletes a demand, resetting invoice status back to `uploaded`.
- **Activation Trigger**: Triggered when user cancels a pending demand submission.

---

### 3.15 `back/routers/admin.py`

**File Overview**:
Contains admin-only endpoints for reviewing demands, inspecting audit logs, and managing users/invoices across the platform. Protected via `Depends(require_admin)`.

---

#### Endpoint: `GET /admin/demands` (`admin_list_demands`)
- **What it does**: Retrieves demands across all users using `selectinload(Demand.invoice)` and `selectinload(Demand.requester)`. Supports filtering by status (`status_filter=pending`).
- **Activation Trigger**: Triggered when admin views the **Admin Pending Review Queue**.

---

#### Endpoint: `PATCH /admin/demands/{demand_id}` (`admin_review_demand`)
- **What it does**: Receives admin decision (`status: "approved"` or `"rejected"`). Updates `demand.status`, `demand.reviewed_by_admin_id`, `demand.reviewed_at`, and `invoice.status`. Writes audit log entry (`APPROVED_DEMAND` or `REJECTED_DEMAND`).
- **Activation Trigger**: Triggered when admin clicks **Approve** or **Reject** button in either the **Admin Review Queue** or the **OCR File Management** view table.
- **Why this method?**: Enforces requirement 2: only admins have authorization to approve or reject pending demands. State transitions are atomic and audited.
- **Example**:
  ```bash
  curl -X PATCH http://127.0.0.1:8000/admin/demands/1 \
    -H "Authorization: Bearer <ADMIN_JWT>" \
    -H "Content-Type: application/json" \
    -d '{"status": "approved"}'
  ```

---

#### Endpoint: `GET /admin/audit` (`admin_audit_logs`)
- **What it does**: Returns full chronological audit trail of system events and admin decisions.
- **Activation Trigger**: Triggered when admin views the System Audit Log panel.

---

#### Endpoints: User & Invoice Management
- `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{id}`, `DELETE /admin/users/{id}`: Enables administrators to view, create, edit, activate/ban user accounts.
- `GET /admin/invoices`, `POST /admin/invoices`, `PATCH /admin/invoices/{id}`, `DELETE /admin/invoices/{id}`: Enables administrators to view, create, update, or remove invoice records directly.

---

### 3.16 `back/routers/dashboard.py`

**File Overview**:
Provides analytical summary metrics for dashboard cards and Power BI intelligence widgets.

---

#### Endpoint: `GET /dashboard/me` (`get_my_dashboard_stats`)
- **What it does**: Computes aggregate metrics for authenticated user:
  - `total_invoices`: Count of user's uploaded invoices.
  - `pending_demands`: Count of user's demands in `pending` status.
  - `validated_demands`: Count of user's demands in `approved` or `validated` status.
  - `total_kwh`: Sum of `kwh_consumed` across user's invoices.
- **Activation Trigger**: Triggered when user opens the Overview Dashboard.
- **Why this method?**: Computes aggregations directly in SQL database engine using SQLAlchemy `func.count()` and `func.sum()`, maximizing query efficiency.

---

## 4. End-to-End Workflow & Execution Trace

1. **User Login**: User submits credentials to `POST /auth/login`. Server verifies bcrypt hash, returns JWT token stored in browser `localStorage`.
2. **Invoice Upload**: User uploads file to `POST /invoices/upload`. Server streams file to `uploads/`, runs Tesseract OCR engine, auto-extracts billing figures, and returns invoice object.
3. **Values Confirmation**: User inspects extracted OCR fields and clicks "Confirm & Save Validated Values". Frontend calls `PUT /invoices/{id}/values`. Backend updates values, creates/sets demand to `pending`, and updates invoice status to `pending`.
4. **Admin Review Queue**: Admin opens review panel (`GET /admin/demands?status=pending`). The pending demand appears in the queue.
5. **Admin Decision**: Admin clicks "Approve". Frontend sends `PATCH /admin/demands/{id}` with `{"status": "approved"}`. Backend sets demand and invoice status to `approved`, logs audit event `APPROVED_DEMAND`, and commits transaction.
6. **Dashboard Refresh**: User dashboard queries `GET /invoices/mine` and `GET /dashboard/me`, showing updated status **Approved** with live DB metrics.
