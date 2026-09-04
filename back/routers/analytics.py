"""
analytics.py - Power BI Embed URL Router
==========================================
Serves the Power BI "Publish to Web" embed URL to the frontend.

Setup (one-time):
  1. In Power BI Service (app.powerbi.com), open your published report.
  2. Click: File -> Embed report -> Publish to web (public)
  3. Copy the iframe src URL (e.g. https://app.powerbi.com/reportEmbed?reportId=...)
  4. Set the environment variable POWERBI_EMBED_URL to that URL, e.g.:
       On Windows PowerShell:
         $env:POWERBI_EMBED_URL = "https://app.powerbi.com/reportEmbed?reportId=..."
       Or create a back/.env file and add:
         POWERBI_EMBED_URL=https://app.powerbi.com/reportEmbed?reportId=...
  5. Restart the backend - the Analytics tab will show the live report.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from config import settings
from deps import get_current_user

logger = logging.getLogger("invoiceflow.analytics")

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/embed-url")
def get_embed_url(current_user=Depends(get_current_user)):
    """
    Returns the Power BI Publish-to-Web embed URL for the analytics iframe.
    Accessible to all authenticated users (both admin and user).
    """

    if not settings.POWERBI_EMBED_URL:
        logger.warning(
            "POWERBI_EMBED_URL is not configured. "
            "Set it as an environment variable to enable the analytics dashboard."
        )
        return {"configured": False, "embed_url": None}

    logger.info(
        "Serving Power BI embed URL to user: %s",
        getattr(current_user, "email", getattr(current_user, "id", "?"))
    )
    return {"configured": True, "embed_url": settings.POWERBI_EMBED_URL}
