"""Streamlit-free wrapper around the OCR engine in ocr/gold.py.

Exposes a single function ``run_ocr(file_path)`` that accepts a path to a
saved PDF/image file and returns a dict with the extracted STEG bill fields
mapped to the database schema.

This module is imported by the invoices router to auto-populate invoice rows
after upload.
"""
import logging
import os
import time
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

# Target canvas: US Letter at 300 DPI (8.5 x 11.0 inches)
TARGET_LETTER_W = 2550
TARGET_LETTER_H = 3300


def trim_scanner_margins(img: np.ndarray, max_margin_pct: float = 0.25) -> np.ndarray:
    """Trim uniform outer white/scanner margins (Specification Section 11).

    If an invoice (e.g. A4/A5) was scanned or placed in the center of an A3 canvas,
    large empty margins exist around the actual content. Trimming them ensures
    the invoice content itself scales to fill the Letter height properly.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape[:2]

    # Downscale for fast robust thresholding
    small = cv2.resize(gray, (800, int(800 * (h / w))), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]

    # Binary mask: dark ink on light background
    _, thresh = cv2.threshold(small, 245, 255, cv2.THRESH_BINARY_INV)

    # Clean small isolated noise dots
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    pts = cv2.findNonZero(thresh)
    if pts is None:
        return img

    x, y, bw, bh = cv2.boundingRect(pts)

    # Check if there is substantial margin (> 3% on at least 2 sides)
    scale_back_x = w / sw
    scale_back_y = h / sh

    orig_x = int(x * scale_back_x)
    orig_y = int(y * scale_back_y)
    orig_w = int(bw * scale_back_x)
    orig_h = int(bh * scale_back_y)

    margin_left = orig_x / w
    margin_right = (w - (orig_x + orig_w)) / w
    margin_top = orig_y / h
    margin_bottom = (h - (orig_y + orig_h)) / h

    # Only crop if there are significant outer white borders (like an A3 scan of an A4 page)
    if (margin_left > 0.04 or margin_right > 0.04 or margin_top > 0.04 or margin_bottom > 0.04):
        # Keep a small, clean 1.5% padding so outer borders/text are not clipped
        pad_x = int(0.015 * w)
        pad_y = int(0.015 * h)
        x0 = max(0, orig_x - pad_x)
        y0 = max(0, orig_y - pad_y)
        x1 = min(w, orig_x + orig_w + pad_x)
        y1 = min(h, orig_y + orig_h + pad_y)
        
        # Guard against over-cropping: must preserve at least 50% of the dimension
        if (x1 - x0) > 0.5 * w and (y1 - y0) > 0.5 * h:
            logger.info("Trimmed scanner margins: (%d, %d, %d, %d) from original (%d, %d)", x0, y0, x1, y1, w, h)
            return img[y0:y1, x0:x1]

    return img


def convert_to_us_letter_adobe(img: np.ndarray) -> np.ndarray:
    """Normalize input invoice to canonical US Letter canvas (2550 x 3300 px @ 300 DPI)
    according to the PDF Normalization Specification:

    1. Orientation Check (Sec 2): Ensure portrait.
    2. Scanner Margin Trim (Sec 11): Remove excessive outer white borders (e.g. A4 on A3 bed).
    3. Height Normalization (Sec 4): scale = 3300 / source_height.
    4. Proportional scaling & Horizontal Centering (Sec 5):
       offset_x = (2550 - scaled_width) / 2.
    """
    h, w = img.shape[:2]

    # 1. Orientation check: if landscape, rotate 90 degrees to portrait
    if w > h:
        logger.info("Rotating landscape page (%dx%d) to portrait", w, h)
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        h, w = img.shape[:2]

    # 2. Section 11: Content Bounding Box trimming (handles large outer margins)
    img = trim_scanner_margins(img)
    h, w = img.shape[:2]

    # If already exact canonical letter size, return as is
    if h == TARGET_LETTER_H and w == TARGET_LETTER_W:
        return img

    # 3. Section 4 & Section 3: Uniform scaling by height (preserving aspect ratio)
    scale = TARGET_LETTER_H / h
    new_w = int(round(w * scale))
    new_h = TARGET_LETTER_H

    # Safety guard: if width exceeds 2550 px, scale uniformly to fit width
    if new_w > TARGET_LETTER_W:
        scale = TARGET_LETTER_W / w
        new_w = TARGET_LETTER_W
        new_h = int(round(h * scale))

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # 4. Section 5: Place onto 2550 x 3300 white canvas and center horizontally
    if len(img.shape) == 3:
        canvas = np.full((TARGET_LETTER_H, TARGET_LETTER_W, img.shape[2]), 255, dtype=np.uint8)
    else:
        canvas = np.full((TARGET_LETTER_H, TARGET_LETTER_W), 255, dtype=np.uint8)

    top = (TARGET_LETTER_H - new_h) // 2
    left = (TARGET_LETTER_W - new_w) // 2

    canvas[top : top + new_h, left : left + new_w] = resized
    logger.info(
        "Normalized document to US Letter (2550x3300): new_w=%d, new_h=%d, offset_x=%d, offset_y=%d",
        new_w, new_h, left, top
    )
    return canvas



MAX_MONETARY_LIMIT = Decimal("9999999.999")


def _safe_decimal(value_str: str | None) -> Decimal | None:
    """Convert an OCR-extracted number string to Decimal, or None."""
    if not value_str or value_str == "Not Found" or value_str == "0":
        return None
    try:
        cleaned = value_str.strip().replace(" ", "").replace(",", ".")
        val = abs(Decimal(cleaned))
        # Prevent database Arithmetic Overflow on OCR run-on digit glitches
        if val > MAX_MONETARY_LIMIT:
            logger.warning("Rejecting out-of-bounds OCR monetary amount: %s", val)
            return None
        return val
    except (InvalidOperation, ValueError):
        return None


def _safe_int(value, default: int = 0) -> int:
    """Convert an OCR-extracted integer value (int or str) to int."""
    if value is None or value == "Not Found":
        return default
    try:
        val = abs(int(str(value).strip().replace(" ", "").replace(",", "")))
        if val > 99999999:
            return default
        return val
    except (ValueError, TypeError):
        return default


def _safe_decimal_tariff(value_str: str | None) -> Decimal | None:
    """Like _safe_decimal but treats '0' and '0.000' as valid zero (not None)."""
    if value_str is None or value_str == "Not Found":
        return None
    try:
        cleaned = str(value_str).strip().replace(" ", "").replace(",", ".")
        val = abs(Decimal(cleaned))
        if val > MAX_MONETARY_LIMIT:
            logger.warning("Rejecting out-of-bounds OCR tariff amount: %s", val)
            return None
        return val
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
    start_time = time.perf_counter()

    # --- Load image -----------------------------------------------------------
    if abs_path.lower().endswith(".pdf"):
        if convert_from_path is None:
            raise RuntimeError(
                "pdf2image is not installed. Run: pip install pdf2image"
            )
        pages = convert_from_path(abs_path, poppler_path=POPPLER_PATH, dpi=300)
        img = cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(abs_path)
        if img is None:
            raise RuntimeError(f"Could not read image file: {abs_path}")

    # Convert to Adobe US Letter (8.5 x 11 in @ 300 DPI: 2550 x 3300 px) preserving aspect ratio
    img = convert_to_us_letter_adobe(img)



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
    mapped["kwh_consumed"] = sum(
        mapped[field]
        for field in (
            "consumption_jour", "consumption_pointe",
            "consumption_soiree", "consumption_nuit",
        )
    )

    processing_time = round(time.perf_counter() - start_time, 2)

    logger.info(
        "OCR complete in %.2fs: status=%s, invoice_no=%s, ttc=%s",
        processing_time,
        ocr_status,
        invoice_no,
        mapped.get("net_a_payer"),
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
            "processing_time": processing_time,
            "time_taken": f"{processing_time}s",
        },
        "mapped": mapped,
        "ocr_status": ocr_status,
        "confidence": confidence,
        "processing_time": processing_time,
    }
