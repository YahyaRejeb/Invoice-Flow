"""Streamlit-free wrapper around the OCR engine in ocr/gold.py.

Exposes a single function ``run_ocr(file_path)`` that accepts a path to a
saved PDF/image file and returns a dict with the extracted STEG bill fields
mapped to the database schema.

This module is imported by the invoices router to auto-populate invoice rows
after upload.
"""
import logging
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

import cv2
import numpy as np

from ocr.gold import (
    PDF_SUPPORT,
    POPPLER_PATH,
    calculate_montant_ht,
    compute_extraction_status,
    crop_regions,
    deskew_image,
    parse_steg_bill,
    preprocess_image,
    preprocess_region,
)

# pdf2image is optional — matches the same guard in gold.py
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

# Tesseract is configured by gold.py's module-level code (TESSERACT_PATH,
# TESSDATA_PREFIX, POPPLER_PATH) which fires on the import above.

import pytesseract

logger = logging.getLogger("steg.ocr")


def _safe_decimal(value_str: str | None) -> Decimal | None:
    """Convert an OCR-extracted number string to Decimal, or None."""
    if not value_str or value_str == "Not Found" or value_str == "0":
        return None
    try:
        cleaned = value_str.strip().replace(" ", "").replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _safe_int(value, default: int = 0) -> int:
    """Convert an OCR-extracted integer value (int or str) to int.

    Returns *default* if the value is missing, 'Not Found', or unparseable.
    This is used for consumption values where a missing tariff period means
    zero consumption, not an OCR failure.
    """
    if value is None or value == "Not Found":
        return default
    try:
        return int(str(value).strip().replace(" ", "").replace(",", ""))
    except (ValueError, TypeError):
        return default


def _safe_decimal_tariff(value_str: str | None) -> Decimal | None:
    """Like _safe_decimal but treats '0' and '0.000' as valid zero (not None).

    Used for summary monetary rows where zero is a legitimate financial value
    and must not be confused with an extraction failure.
    """
    if value_str is None or value_str == "Not Found":
        return None
    try:
        cleaned = str(value_str).strip().replace(" ", "").replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _parse_ocr_date(date_str: str | None) -> str | None:
    """Convert OCR date format ``'MM/YYYY'`` to ISO ``'YYYY-MM-01'``.

    Returns None if the string is missing or unparseable.
    """
    if not date_str or date_str == "Not Found":
        return None
    # Expected format: "09/2024"
    parts = date_str.strip().split("/")
    if len(parts) == 2:
        month, year = parts
        try:
            m = int(month)
            y = int(year)
            if 1 <= m <= 12 and 1900 <= y <= 2100:
                return f"{y:04d}-{m:02d}-01"
        except ValueError:
            pass
    return None


def run_ocr(file_path: str) -> dict:
    """Run the full STEG bill OCR pipeline on a saved file.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the uploaded PDF or image file.

    Returns
    -------
    dict with keys:
        - ``ocr_raw``: the raw OCR output dict from ``parse_steg_bill``
        - ``mapped``: fields mapped to database column names & types
        - ``ocr_status``: ``"validate"`` / ``"review"`` / ``"invalid"``
        - ``confidence``: per-field confidence dict from the OCR engine
    """
    abs_path = str(Path(file_path).resolve())
    logger.info("Starting OCR on %s", abs_path)

    # --- Load image -----------------------------------------------------------
    if abs_path.lower().endswith(".pdf"):
        if convert_from_path is None:
            raise RuntimeError(
                "pdf2image is not installed. Run: pip install pdf2image"
            )
        pages = convert_from_path(abs_path, poppler_path=POPPLER_PATH, dpi=300)
        img = np.array(pages[0])
    else:
        img = cv2.imread(abs_path)
        if img is None:
            raise RuntimeError(f"Could not read image file: {abs_path}")

    # --- Pre-process ----------------------------------------------------------
    gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    gray_full = deskew_image(gray_full)
    header_crop, amounts_crop = crop_regions(gray_full)

    texts: dict[str, str] = {}
    if header_crop is not None:
        processed_header = preprocess_region(header_crop, scale=3)
        texts["header"] = pytesseract.image_to_string(
            processed_header, lang="fra", config="--psm 6"
        )
    if amounts_crop is not None:
        processed_amounts = preprocess_region(amounts_crop, scale=4)
        texts["amounts"] = pytesseract.image_to_string(
            processed_amounts, lang="fra", config="--psm 6"
        )
    processed_full = preprocess_image(img)
    texts["full"] = pytesseract.image_to_string(
        processed_full, lang="fra", config="--psm 6"
    )

    # --- Parse ----------------------------------------------------------------
    parsed = parse_steg_bill(gray_full, texts, hints={"facture": "62"})

    # Pull out internal keys
    confidence = parsed.pop("_confidence", {})
    parsed.pop("_calibration_profile", None)
    cross_match = parsed.get("net_a_payer_cross_check_match")

    ocr_status = parsed.get("status", "invalid")

    # --- Map to database columns ----------------------------------------------
    invoice_date_iso = _parse_ocr_date(parsed.get("date"))
    amount_excl_tax = _safe_decimal(parsed.get("montant ht"))
    tva = _safe_decimal(parsed.get("total_3(taxes)"))
    amount_incl_tax = _safe_decimal(parsed.get("montant ttc"))
    invoice_no = parsed.get("facture")
    if invoice_no == "Not Found":
        invoice_no = None
    address = parsed.get("address")
    if address == "Not Found":
        address = None

    mapped = {
        "invoice_no": invoice_no,
        "address": address,
        "invoice_date": invoice_date_iso,
        "amount_excl_tax": float(amount_excl_tax) if amount_excl_tax else None,
        "tva": float(tva) if tva else None,
        "amount_incl_tax": float(amount_incl_tax) if amount_incl_tax else None,
        "currency": "TND",
        # --- Detailed tariff breakdown (STEG OCR Expansion) ---
        # Consommation per period — missing period = 0 (not an OCR failure)
        "consumption_jour":   _safe_int(parsed.get("consumption_jour"), 0),
        "consumption_pointe": _safe_int(parsed.get("consumption_pointe"), 0),
        "consumption_soiree": _safe_int(parsed.get("consumption_soiree"), 0),
        "consumption_nuit":   _safe_int(parsed.get("consumption_nuit"), 0),
        # Prix Unitaire per period — missing period = 0
        "pu_jour":   _safe_int(parsed.get("pu_jour"), 0),
        "pu_pointe": _safe_int(parsed.get("pu_pointe"), 0),
        "pu_soiree": _safe_int(parsed.get("pu_soiree"), 0),
        "pu_nuit":   _safe_int(parsed.get("pu_nuit"), 0),
        # Detailed Montant per period — missing period = 0.000
        "montant_jour":   _safe_decimal_tariff(parsed.get("montant_jour")),
        "montant_pointe": _safe_decimal_tariff(parsed.get("montant_pointe")),
        "montant_soiree": _safe_decimal_tariff(parsed.get("montant_soiree")),
        "montant_nuit":   _safe_decimal_tariff(parsed.get("montant_nuit")),
        # Summary monetary rows — None means extraction failed (not zero)
        "sous_total":  _safe_decimal_tariff(parsed.get("sous_total")),
        "total_1":     _safe_decimal_tariff(parsed.get("total_1")),
        "total_2":     _safe_decimal_tariff(parsed.get("total_2")),
        "total_3":     _safe_decimal_tariff(parsed.get("total_3")),
        "net_a_payer": _safe_decimal_tariff(
            parsed.get("net_a_payer") or parsed.get("montant ttc")
        ),
    }

    logger.info(
        "OCR complete: status=%s, invoice_no=%s, ttc=%s",
        ocr_status,
        invoice_no,
        amount_incl_tax,
    )

    return {
        "ocr_raw": {
            # --- Existing fields (backward compatible) ---
            "consomateur": parsed.get("consomateur", "Not Found"),
            "address": parsed.get("address", "Not Found"),
            "facture": parsed.get("facture", "Not Found"),
            "date": parsed.get("date", "Not Found"),
            "montant_ht": parsed.get("montant ht", "Not Found"),
            "total_3_taxes": parsed.get("total_3(taxes)", "Not Found"),
            "montant_ttc": parsed.get("montant ttc", "Not Found"),
            "devise": "TND",
            "net_a_payer_table_reading": parsed.get("net_a_payer_table_reading"),
            "net_a_payer_coupon_reading": parsed.get("net_a_payer_coupon_reading"),
            "net_a_payer_cross_check_match": cross_match,
            # --- New structured tariff fields (STEG OCR Expansion) ---
            "consommation_detaillee": {
                "jour":   _safe_int(parsed.get("consumption_jour"), 0),
                "pointe": _safe_int(parsed.get("consumption_pointe"), 0),
                "soiree": _safe_int(parsed.get("consumption_soiree"), 0),
                "nuit":   _safe_int(parsed.get("consumption_nuit"), 0),
            },
            "prix_unitaire": {
                "jour":   _safe_int(parsed.get("pu_jour"), 0),
                "pointe": _safe_int(parsed.get("pu_pointe"), 0),
                "soiree": _safe_int(parsed.get("pu_soiree"), 0),
                "nuit":   _safe_int(parsed.get("pu_nuit"), 0),
            },
            "montant_detaille": {
                "jour":   parsed.get("montant_jour", "0.000"),
                "pointe": parsed.get("montant_pointe", "0.000"),
                "soiree": parsed.get("montant_soiree", "0.000"),
                "nuit":   parsed.get("montant_nuit", "0.000"),
            },
            "sous_total":  parsed.get("sous_total"),
            "total_1":     parsed.get("total_1"),
            "total_2":     parsed.get("total_2"),
            "total_3":     parsed.get("total_3") or parsed.get("total_3(taxes)"),
            "net_a_payer": parsed.get("net_a_payer") or parsed.get("montant ttc"),
        },
        "mapped": mapped,
        "ocr_status": ocr_status,
        "confidence": confidence,
    }
