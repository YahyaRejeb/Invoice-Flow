# InvoiceFlow AI — Facture Processing & Analytics Portal

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-MSSQL-CC292B.svg?logo=microsoftsqlserver&logoColor=white)](https://www.microsoft.com/sql-server)
[![Tesseract OCR](https://img.shields.io/badge/OCR-Tesseract%205-5C8DBC.svg)](https://github.com/tesseract-ocr/tesseract)
[![JWT Auth](https://img.shields.io/badge/Auth-JWT%20%2B%20Bcrypt-000000.svg?logo=jsonwebtokens)](https://jwt.io)
[![Power BI](https://img.shields.io/badge/Analytics-Power%20BI-F2C811.svg?logo=powerbi&logoColor=black)](https://powerbi.microsoft.com/)

**InvoiceFlow** is an enterprise-grade document intelligence, invoice verification, and business analytics platform tailored for electricity and gas invoices (**STEG — Société Tunisienne de l'Électricité et du Gaz**). It combines an intelligent computer vision/OCR pipeline, a high-performance REST backend, role-based workflows, an AI-powered Text-to-SQL admin assistant, and interactive Power BI analytics into a unified glassmorphism dashboard.

---

## 🌟 Key Features

### 📄 Intelligent OCR & Computer Vision Pipeline
- **Automated Document Preprocessing**: Auto-deskewing, adaptive thresholding, scanner margin trimming (Section 11 specification), and 300 DPI Letter normalization (`2550 x 3300`).
- **STEG Domain-Specific Parser**: Precision extraction of critical bill fields:
  - Client Reference & Bill Number (`Numéro Facture`, `Référence`)
  - District code, meter indices, and consumption periods
  - Electricity & Gas index readings (`Ancien / Nouveau Index`, `Consommation`)
  - Tariff breakdown, municipal fees, and value-added tax (`Montant HT`, `TVA`, `RTT`, `Net à Payer`)
- **Mathematical Integrity Validation**: Validates tax and subtotal consistency (`Montant HT + Taxes == Net à Payer`) and computes extraction confidence scores.

### 🛡️ Role-Based Access Control & Audit
- **JWT Stateless Authentication**: Secure password hashing with salted `bcrypt` and signed JWT bearer tokens (`HS256`).
- **Granular Permissions**:
  - **User Portal**: Upload bills, review parsed fields, submit demands, and track payment statuses.
  - **Admin Control Center**: Review queue for invoice approval/rejection, user account approval, and comprehensive system audit trail.

### 🤖 RAG AI Admin Chatbot (Text-to-SQL Assistant)
- **Multi-Model Sequential Fallback Chain**:
  1. **Groq** (`openai/gpt-oss-120b`) — Fast SQL generation
  2. **Groq** (`llama-3.3-70b-versatile`) — Free-tier fallback
  3. **Groq** (`gemma2-9b-it`) — Lightweight fast inference
  4. **OpenRouter** (`openrouter/auto`) — Provider routing
  5. **Rule-Based Engine** — Zero-network fallback for standard queries
- **Strict SQL Safety Validator**: AST / keyword sanitizer blocking any mutating statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `EXEC`) to ensure read-only database interaction.
- **Natural Language Synthesis**: Translates complex SQL query outputs into polished executive summaries and markdown tables.

### 📊 Business Intelligence & Analytics
- **Interactive Overview**: Live KPI widgets tracking total spending, volume, treated vs. pending invoices, and approval rates.
- **Power BI Embedded Dashboard**: Deep integration for energy consumption trends, regional heatmaps, and financial analytics.
- **Modern Glassmorphic UI**: Ambient dynamic gradients, dark/light theme switching, and responsive design.

---

## 🏗️ Architecture & Project Structure

```
Projet PFA_FR/
├── index.html               # Main Single-Page Application (SPA) dashboard
├── start_backend.bat        # Quick-start script for backend server
├── restart_backend.bat      # Helper script to terminate and reboot backend
├── BACKEND_GUIDE.md         # Detailed technical backend reference
├── back/                    # FastAPI Backend
│   ├── main.py              # Application entry point, CORS, routers & lifespan
│   ├── config.py            # Central configuration & database connection parameters
│   ├── database.py          # SQLAlchemy engine, session maker & schema migrations
│   ├── deps.py              # Auth & RBAC dependencies
│   ├── models.py            # SQLAlchemy database models
│   ├── schemas.py           # Pydantic v2 schemas
│   ├── security.py          # Bcrypt hashing & JWT token management
│   ├── services.py          # File storage & audit logging service
│   ├── seed.py              # Seed script for initial demo accounts
│   ├── requirements.txt     # Python backend dependencies
│   ├── chatbot/             # AI Admin Chatbot (Text-to-SQL RAG)
│   │   ├── config.py        # Model chain configuration & credentials
│   │   ├── service.py       # Orchestration pipeline
│   │   ├── sql_generator.py # Prompting & LLM SQL generation
│   │   ├── sql_validator.py # Read-only query security validator
│   │   ├── executor.py      # SQLAlchemy query execution
│   │   └── synthesizer.py   # Natural language answer synthesis
│   ├── ocr/                 # OCR engine & algorithms
│   │   ├── gold.py          # Vision processing, contouring & regex extraction
│   │   └── Tesseract-OCR/   # Bundled OCR binary & language models
│   ├── ocr_service.py       # High-level OCR service wrapper
│   └── routers/             # FastAPI REST Routers
│       ├── admin.py         # Admin management, review queue & audit logs
│       ├── auth.py          # Login, registration, profile & password reset
│       ├── dashboard.py     # Analytics & metric aggregation endpoints
│       ├── demands.py       # User demand management
│       └── invoices.py      # Invoice upload, OCR trigger & verification
├── front/                   # Frontend assets
│   ├── css/                 # Design system (variables, components, animations, dashboard)
│   └── js/                  # Client logic (API client, Auth, UI, Chatbot, Tables)
└── uploads/                 # Storage for uploaded invoices and PDF documents
```

---

## ⚙️ Tech Stack

- **Backend**: Python 3.10+, [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [Pydantic v2](https://docs.pydantic.dev/), [Uvicorn](https://www.uvicorn.org/)
- **Database**: Microsoft SQL Server / LocalDB via [pyodbc](https://github.com/mkleehammer/pyodbc) (ODBC Driver 18)
- **Computer Vision / OCR**: OpenCV (`cv2`), [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), `pdf2image`, `poppler`
- **AI / LLM Providers**: [Groq](https://groq.com/) & [OpenRouter](https://openrouter.ai/)
- **Security**: `python-jose`, `bcrypt`
- **Frontend**: Vanilla HTML5/CSS3, Modern ES6+ JavaScript, FontAwesome 6, Google Fonts (Outfit, Plus Jakarta Sans, Fira Code)

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10 or higher**
- **Microsoft SQL Server** (LocalDB or standard instance) with database named `StegDB` (or custom name via `.env`)
- **ODBC Driver 18 for SQL Server** installed on Windows
- *(Optional)* Poppler and Tesseract OCR binaries (pre-configured paths available in `back/ocr/`)

### 2. Environment Configuration
Create a `.env` file in `back/` or configure environment variables in your system:

```ini
# Database Configuration
INVOICEFLOW_DB_SERVER=SE7LLI
INVOICEFLOW_DB_NAME=StegDB
INVOICEFLOW_DB_DRIVER=ODBC Driver 18 for SQL Server

# JWT Authentication
INVOICEFLOW_JWT_SECRET=your-super-secure-jwt-secret-key-here
INVOICEFLOW_JWT_EXPIRE_MINUTES=720

# AI Chatbot Credentials (Optional - set if using LLM features)
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Server settings
INVOICEFLOW_HOST=127.0.0.1
INVOICEFLOW_PORT=8000
INVOICEFLOW_SEED=0
```

### 3. Installation
Open a terminal in the project directory and create a virtual environment:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r back/requirements.txt
```

### 4. Running the Application

#### Option A: Using the provided Batch script (Windows)
Double-click or run:
```powershell
.\start_backend.bat
```

#### Option B: Using Uvicorn directly
```powershell
cd back
uvicorn main:app --reload --port 8000 --log-level info
```

Once started:
- **Web Application**: Navigate to [http://localhost:8000/](http://localhost:8000/) in your browser.
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative API Docs (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔒 Security Best Practices

- **Never commit `.env` or API keys**: Store all sensitive credentials (`GROQ_API_KEY`, `OPENROUTER_API_KEY`, `INVOICEFLOW_JWT_SECRET`) in environment variables or untracked `.env` files.
- **SQL Sanitization**: All queries executed through the Chatbot assistant pass through `chatbot/sql_validator.py` ensuring read-only permissions (`SELECT` / `WITH` only).
- **Authentication**: All sensitive administrative endpoints enforce role verification through FastAPI dependencies (`deps.require_admin`).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
