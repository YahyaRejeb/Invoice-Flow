"""InvoiceFlow Facture Processing Platform - FastAPI backend entry point.

Serves the REST API under /api routes (/auth, /invoices, /demands, /admin, ...)
AND the static frontend (index.html + assets) at the root, so the whole
application runs on a single origin.

Run:  uvicorn main:app --reload --port 8000
  or: python run.py
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import PROJECT_DIR, UPLOADS_DIR, settings
from database import SessionLocal, init_db
from database import get_db  # noqa: F401  (exported for convenience)
from routers import admin, analytics, auth, chatbot, dashboard, demands, invoices
from seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("invoiceflow")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.SEED:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
    else:
        logger.info("Seeding disabled (INVOICEFLOW_SEED=0)")
    yield


app = FastAPI(
    title="InvoiceFlow API",
    description="FastAPI backend for InvoiceFlow invoice processing, validation and demand workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

# Per-dev flexibility (opening index.html directly from disk uses the "null"
# origin). Restrict this list before any production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- API routes ----
app.include_router(auth.router)
app.include_router(invoices.router)
app.include_router(demands.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(chatbot.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "invoiceflow-backend", "version": app.version}


# ---- Static frontend ----
FRONT_DIR = PROJECT_DIR / "front"
INDEX_FILE = PROJECT_DIR / "index.html"

# index.html loads its styles/scripts from /front/css & /front/js.
app.mount("/front", StaticFiles(directory=FRONT_DIR), name="front")
# Legacy alias for assets served from the front directory.
app.mount("/assets", StaticFiles(directory=FRONT_DIR), name="assets")
# Uploaded OCR documents and scanned files.
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(INDEX_FILE)
