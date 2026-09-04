import os
import pytesseract
from pytesseract import Output
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path(__file__).parent
TESSERACT_PATH = BASE_DIR / "Tesseract-OCR" / "tesseract.exe"
if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)

TESSDATA_PATH = BASE_DIR / "Tesseract-OCR" / "tessdata"
if TESSDATA_PATH.exists():
    os.environ['TESSDATA_PREFIX'] = str(TESSDATA_PATH)

POPPLER_PATH = BASE_DIR / "poppler-26.02.0" / "Library" / "bin"

# ==========================================
# REST OF THE IMPORTS
# ==========================================
import cv2
import re
import json
import difflib
try:
    import streamlit as st
except ImportError:
    st = None
import numpy as np
import tempfile
from collections import Counter

try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

def four_point_transform(image, pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def correct_perspective(image):
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 75, 200)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(c) > (image.shape[0] * image.shape[1] * 0.25):
                return four_point_transform(image, approx.reshape(4, 2))
    except Exception:
        pass
    return image

def deskew_image(gray):
    try:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle
        else:
            angle = -angle
        if 0.5 < abs(angle) <= 5.0:
            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            return rotated
    except Exception:
        pass
    return gray

def enhance_and_binarize(gray):
    up = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
    # PERF: fastNlMeansDenoising (searchWindowSize=21) measured at ~8.8s per call on a
    # full invoice page -- by far the single biggest cost in the pipeline (profiled at
    # ~50% of total runtime across all its call sites). bilateralFilter is edge-preserving
    # (keeps character edges crisp for OCR, unlike a plain Gaussian blur) and is orders of
    # magnitude cheaper because it doesn't do NLM's exhaustive search-window patch matching.
    # These invoices are clean PDF renders (no sensor noise), so NLM's extra quality over
    # bilateral was never actually buying anything here.
    denoised = cv2.bilateralFilter(up, d=7, sigmaColor=50, sigmaSpace=50)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)
    bright = cv2.convertScaleAbs(contrast, alpha=1.0, beta=15)
    blurred = cv2.GaussianBlur(bright, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(bright, 1.0 + 1.5, blurred, -1.5, 0)
    binary = cv2.adaptiveThreshold(
        sharpened, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 7
    )
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open, iterations=1)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    processed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_close, iterations=1)
    return processed

def preprocess_image(image_array):
    corrected = correct_perspective(image_array)
    if len(corrected.shape) == 3:
        gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
    else:
        gray = corrected
    gray = deskew_image(gray)
    return enhance_and_binarize(gray)

def preprocess_region(gray_crop, scale=3):
    up = cv2.resize(gray_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    # PERF: see enhance_and_binarize -- same NLM-to-bilateral swap, same reasoning.
    denoised = cv2.bilateralFilter(up, d=5, sigmaColor=40, sigmaSpace=40)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(denoised)
    blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(enhanced, 2.0, blurred, -1.0, 0)
    _, otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return otsu

# FIX 1: widened from (0.055, 0.10, ...) -- on the bill this was tested against,
# "Mois 09/2024" sits right at the 0.096-0.10 boundary and was getting clipped,
# so mois fell through to a full-page date scan and grabbed the wrong date.
HEADER_BOX = (0.055, 0.115, 0.0, 1.0)
AMOUNTS_BOX = (0.55, 0.86, 0.015, 0.16)
MIN_DIM_FOR_CROPPING = 300

# FIX 2: dedicated crop for the "Consommateur" field. STEG bills print two
# separate names side by side on the same row -- "Payeur" (left) and
# "Consommateur" (right) -- and the old regex only recognised
# Abonné/Client/Raison Sociale/Nom, none of which match "Consommateur", so it
# fell back to a generic "line containing STE" scan that grabbed the WRONG
# name (Payeur instead of Consommateur). This isolates the right-hand column
# so OCR reads only that field instead of both merged together.
#
# FIX 7: this box is now also the search region for "Adresse", for the same
# reason -- STEG bills print Payeur's Adresse (left) and Consommateur's
# Adresse (right) directly below the Payeur/Consommateur row, so isolating
# the right-hand column is required for BOTH fields, not just the name.
# Verified against a real sample: this exact box captures "Consommateur" on
# its own OCR line and "Adresse" on the very next OCR line, both inside the
# box (see label-scan helpers below).
CONSUMER_BOX = (0.163, 0.207, 0.42, 1.0)

# ==========================================
# LABEL-SCAN EXTRACTION (image_to_data based)
# ==========================================
# FIX 7: this replaces the "crop a fixed fraction box -> OCR to a flat string
# -> regex over the blob" approach for label:value fields (consomateur,
# address, facture, mois) with a positional approach: OCR the region with
# pytesseract.image_to_data (which returns each recognised word's own
# left/top/width/height plus line/par/block grouping), locate the word(s)
# matching the field's label, and read the value as whatever sits on the
# SAME OCR line to the right of the label. This is what actually lets us
# tell "Payeur" and "Consommateur" (or their two Adresse rows) apart without
# hand-measuring a separate fixed box per field -- the box only needs to be
# generous enough to contain the label, not pinpoint-exact.
#
# Left deliberately UNCHANGED by this: the money fields (Prime de puissance,
# Total 3, NET A PAYER, etc.) via CALIBRATION_PROFILES / read_amount_ensemble.
# That region interleaves French/Arabic RTL columns -- a quick check against
# the real sample showed the current AMOUNTS_BOX only reliably isolates the
# bare digit column, not label text next to it. Blind-widening that crop to
# label-scan it without a verified sample risks the exact "silently wrong
# because the guessed box missed" failure this file's own comments warn
# about elsewhere, so the existing (already cross-checked / ensemble-voted)
# money-field logic stays as is.

def _ocr_words(gray_region, scale=4, psm=6, lang='fra'):
    """OCR a region and return a flat list of recognised words with their
    pixel-space bounding boxes and line grouping, instead of a flat string."""
    if gray_region is None or gray_region.size == 0:
        return []
    processed = preprocess_region(gray_region, scale=scale)
    data = pytesseract.image_to_data(
        processed, lang=lang, config=f'--psm {psm}', output_type=Output.DICT
    )
    words = []
    n = len(data['text'])
    for i in range(n):
        text = data['text'][i].strip()
        if not text:
            continue
        try:
            conf = float(data['conf'][i])
        except (ValueError, TypeError):
            conf = -1.0
        words.append({
            'text': text,
            'left': data['left'][i],
            'top': data['top'][i],
            'width': data['width'][i],
            'height': data['height'][i],
            'conf': conf,
            'line_key': (data['block_num'][i], data['par_num'][i], data['line_num'][i]),
        })
    return words

def _group_words_by_line(words):
    """Groups OCR words into their source lines (same block/par/line_num),
    each sorted left-to-right, with the line keys ordered top-to-bottom."""
    lines = {}
    for w in words:
        lines.setdefault(w['line_key'], []).append(w)
    for key in lines:
        lines[key].sort(key=lambda item: item['left'])
    ordered_keys = sorted(lines.keys(), key=lambda k: min(item['top'] for item in lines[k]))
    return lines, ordered_keys

def _clean_token(s):
    return re.sub(r'[^a-zA-Z0-9°àâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]', '', s).lower()

# Secondary confidence guard used alongside MAX_VALUE_WORD_GAP above: a
# tail word that is BOTH close to the previous word AND very low confidence
# is still treated as noise (verified against sample 1's edge-of-crop
# artifacts, which scored 0 and 25).
MIN_VALUE_WORD_CONF = 30

def _match_label_token(word_text, pattern, fuzzy_threshold=0.72):
    """Checks whether word_text is (a spelling of) the given label. Returns
    (matched, leftover) -- leftover recovers characters tesseract fused onto
    the label with no space (e.g. 'ConsommateurM' when the source bill has
    no gap between the label and the value's first letter): if the cleaned
    token starts with the label's plain letters and has extra characters
    after them, those are returned (in original case) instead of being
    silently discarded along with the matched label word."""
    token = _clean_token(word_text)
    if not token:
        return False, ''
    plain = re.sub(r'[^a-z]', '', pattern.lower())
    if re.fullmatch(pattern, token, re.IGNORECASE):
        return True, ''
    if plain and token.startswith(plain) and len(token) > len(plain):
        alnum_idx = [i for i, c in enumerate(word_text) if re.match(r'[A-Za-z0-9°]', c)]
        if len(alnum_idx) >= len(plain):
            split_at = alnum_idx[len(plain)]
            return True, word_text[split_at:]
        return True, ''
    if len(plain) >= 4 and len(token) >= 3:
        ratio = difflib.SequenceMatcher(None, token, plain).ratio()
        if ratio >= fuzzy_threshold:
            return True, ''
    return False, ''

def find_label(lines, ordered_keys, label_sequences, x_min=0):
    """Scans OCR lines top-to-bottom for the first occurrence of a label.
    label_sequences is a list of alternative spellings, each itself a list
    of per-token regex patterns (so a two-word label like "N Facture" can
    be matched as two consecutive OCR words). Returns (line_key, index of
    the label's last token within that line, leftover text fused onto that
    token by an OCR segmentation merge) or None."""
    for key in ordered_keys:
        words = lines[key]
        for start in range(len(words)):
            if words[start]['left'] < x_min:
                continue
            for seq in label_sequences:
                if start + len(seq) > len(words):
                    continue
                leftover = ''
                ok = True
                for off, pat in enumerate(seq):
                    matched, this_leftover = _match_label_token(words[start + off]['text'], pat)
                    if not matched:
                        ok = False
                        break
                    if off == len(seq) - 1:
                        leftover = this_leftover
                if ok:
                    return key, start + len(seq) - 1, leftover
    return None

# Maximum horizontal gap (pixels, at the scale=4 crops these label-scan
# helpers always use) between consecutive words for them to still count as
# part of the same value. Measured against two real bills: genuine
# multi-word values (e.g. "RTE DU BAC Z I RADES", "BOULEVARD DE
# L'ENVIRONNEMENT") have inter-word gaps under ~25px, while unrelated text
# that happens to land on the same OCR line (an edge-of-crop artifact, a
# caption bleeding in from elsewhere) sits 400px+ away. A confidence
# threshold alone wasn't reliable for this -- a genuine noise token scored
# 38%, above a threshold picked from a different bill's noise -- so gap
# distance is the primary filter here, with confidence only as a secondary
# check for a token that is BOTH close and low-confidence.
MAX_VALUE_WORD_GAP = 110
def value_right_of_label(lines, key, label_end_idx, leftover_prefix='', strip_chars=' :.-', numeric_mode=False, max_vertical_offset=None):
    """
    Reads whatever sits to the right of the label on its own OCR line.
    Now includes a vertical filter to reject words from other rows even if
    tesseract merged them into the same line.
    """
    words = lines[key]
    label_word = words[label_end_idx]
    right_edge = label_word['left'] + label_word['width']
    prev_right = right_edge

    # Compute a dynamic vertical threshold based on line height
    line_words = words
    heights = [w['height'] for w in line_words]
    if heights:
        median_height = np.median(heights)
    else:
        median_height = 20
    if max_vertical_offset is None:
        max_vertical_offset = int(median_height * 1.5) + 5

    label_center_y = label_word['top'] + label_word['height'] / 2

    kept = []
    for w in words[label_end_idx + 1:]:
        # BUGFIX: this used to compare against `right_edge` (the label word's own
        # reported right edge). Tesseract's bounding boxes can overshoot the actual
        # rendered glyphs -- e.g. "Consommateur" was measured with width=922 (right
        # edge at x=1145) when the value's first word ("STE") genuinely started at
        # x=966, well inside that inflated box. That silently dropped the first value
        # word (a company-name prefix like "STE"/"SOCIETE") every time the label's own
        # OCR box happened to overshoot -- the intermittent wrong-name detections.
        # `words[label_end_idx+1:]` is already sorted left-to-right (see
        # _group_words_by_line), so any word reached here is already positioned after
        # the label in reading order; comparing against the label's own LEFT edge
        # (rather than its unreliable measured right edge) is enough to reject a truly
        # out-of-order/duplicate token without punishing a value word for the label
        # box being too wide.
        if w['left'] < label_word['left']:
            continue

        # Vertical filter: only accept words near the label's vertical centre
        word_center_y = w['top'] + w['height'] / 2
        if abs(word_center_y - label_center_y) > max_vertical_offset:
            continue

        if numeric_mode:
            # In numeric mode, only collect purely numeric tokens
            if re.fullmatch(r'[\d\s.,-]+', w['text']):
                kept.append(w['text'])
                prev_right = w['left'] + w['width']
            else:
                break
        else:
            gap = w['left'] - prev_right
            if kept and gap > MAX_VALUE_WORD_GAP:
                break
            if gap > MAX_VALUE_WORD_GAP / 2 and w.get('conf', 100) < MIN_VALUE_WORD_CONF:
                break
            kept.append(w['text'])
            prev_right = w['left'] + w['width']

    value = ' '.join(kept)
    if leftover_prefix:
        value = (leftover_prefix + ' ' + value).strip()
    value = ' '.join(value.split()).strip(strip_chars)
    return value or None


def label_scan_field(gray_full, box, label_sequences, x_min=0, scale=4, min_len=1, numeric_mode=False):
    """
    End-to-end: crop `box`, OCR it with position data, find the label,
    return the value on its line. If numeric_mode is True, only consecutive
    numeric tokens are returned.
    """
    crop = crop_box(gray_full, box)
    words = _ocr_words(crop, scale=scale)
    if not words:
        return None
    lines, ordered_keys = _group_words_by_line(words)
    match = find_label(lines, ordered_keys, label_sequences, x_min=x_min)
    if not match:
        return None
    key, idx, leftover = match
    value = value_right_of_label(
        lines, key, idx,
        leftover_prefix=leftover,
        numeric_mode=numeric_mode
    )
    if value and len(value) >= min_len:
        return value
    return None

def label_scan_field(gray_full, box, label_sequences, x_min=0, scale=4, min_len=1, numeric_mode=False):
    """
    End-to-end: crop `box`, OCR it with position data, find the label,
    return the value on its line. If numeric_mode is True, the returned value
    will be only the consecutive numeric tokens after the label.
    """
    crop = crop_box(gray_full, box)
    words = _ocr_words(crop, scale=scale)
    if not words:
        return None
    lines, ordered_keys = _group_words_by_line(words)
    match = find_label(lines, ordered_keys, label_sequences, x_min=x_min)
    if not match:
        return None
    key, idx, leftover = match
    value = value_right_of_label(lines, key, idx, leftover_prefix=leftover, numeric_mode=numeric_mode)
    if value and len(value) >= min_len:
        return value
    return None

# ==========================================
# DEPRECATED: Dynamic Amount Extraction by Label (kept for reference)
# ==========================================
# This function is no longer used. It was too permissive and could pick
# the wrong row. Use label_scan_field with numeric_mode=True instead.
def scan_amounts_by_label(gray_full, y0, y1, label_patterns, x_span=(0.0, 0.35)):
    """
    [DEPRECATED] Do not use. Kept for backward compatibility if any external code calls it.
    """
    h, w = gray_full.shape[:2]
    box = (y0, y1, x_span[0], x_span[1])
    crop = crop_box(gray_full, box)
    if crop.size == 0:
        return None

    words = _ocr_words(crop, scale=4, psm=6)
    if not words:
        return None

    lines, ordered_keys = _group_words_by_line(words)

    for key in ordered_keys:
        line_words = lines[key]
        line_text = ' '.join(word['text'] for word in line_words)

        label_seen = False
        for pat in label_patterns:
            if re.search(pat, line_text, re.IGNORECASE):
                label_seen = True
                break
        if not label_seen:
            continue

        for word in line_words:
            cleaned = clean_number(word['text'])
            if re.match(r'^\d+([\.,]\d+)?$', cleaned):
                return cleaned

    return None

FACTURE_LABEL_SEQUENCES = [
    [r'n', r'facture'],
    [r'facture'],
    [r'numero'],
]
MOIS_LABEL_SEQUENCES = [[r'mois']]
CONSOMMATEUR_LABEL_SEQUENCES = [[r'consommateur'], [r'consommat']]
ADDRESS_LABEL_SEQUENCES = [[r'adresse'], [r'adress'], [r'adr']]
PU_LABEL_SEQUENCES = [[r'p\.?u'], [r'p\.?\s*u'], [r'prix', r'unitaire']]

# NEW: label sequences for money fields (Total 3 and NET A PAYER)
TOTAL3_LABEL_SEQUENCES = [
    [r'total', r'3'],
    [r'total', r'iii'],
    [r'total', r'taxes'],
]
NET_PAYER_LABEL_SEQUENCES = [
    [r'net', r'[àa]', r'payer'],
    [r'montant', r'ttc'],
]

# ==========================================
# CALIBRATION PROFILES
# ==========================================
# (Comments retained for clarity)
CALIBRATION_PROFILES = [
    {
        "name": "profile_A_1098x1433",
        "ref_size": (1098, 1433),
        "prime_puissance_row": (0.6450, 0.6635, 0.0, 0.17),
        "total3_taxes_row":    (0.8017, 0.8186, 0.0, 0.16),
        "recouvrement_row":    (0.8259, 0.8408, 0.0, 0.16),
        "net_a_payer_row":     (0.8530, 0.8780, 0.0, 0.16),
        "coupon_montant_row":  (0.9480, 0.9740, 0.827, 0.905),
    },
    {
        "name": "profile_B_659x876",
        "ref_size": (659, 876),
        "prime_puissance_row": (0.6280, 0.6630, 0.0, 0.22),
        "total3_taxes_row":    (0.7890, 0.8090, 0.0, 0.20),
        "recouvrement_row":    None,
        "net_a_payer_row":     (0.8330, 0.8600, 0.0, 0.22),
        "coupon_montant_row":  (0.9400, 0.9680, 0.83, 0.93),
    },
]

def pick_calibration_profile(gray_full):
    """Picks the calibration profile based on aspect ratio."""
    h, w = gray_full.shape[:2]
    aspect = w / h
    best, best_diff = None, None
    for profile in CALIBRATION_PROFILES:
        rw, rh = profile["ref_size"]
        diff = abs(aspect - (rw / rh))
        if best_diff is None or diff < best_diff:
            best, best_diff = profile, diff
    return best

CROSS_CHECK_MISMATCH_IS_LOW_CONFIDENCE = 0.0
MIN_AGREEMENT_VOTES = 2
AMOUNT_X_STRETCH_FACTORS = (1.0, 1.5)

def crop_regions(gray_full):
    h, w = gray_full.shape[:2]
    if h < MIN_DIM_FOR_CROPPING or w < MIN_DIM_FOR_CROPPING:
        return None, None
    hy0, hy1, hx0, hx1 = HEADER_BOX
    ay0, ay1, ax0, ax1 = AMOUNTS_BOX
    header = gray_full[int(h*hy0):int(h*hy1), int(w*hx0):int(w*hx1)]
    amounts = gray_full[int(h*ay0):int(h*ay1), int(w*ax0):int(w*ax1)]
    return header, amounts

def crop_box(gray_full, box):
    h, w = gray_full.shape[:2]
    y0, y1, x0, x1 = box
    return gray_full[int(h*y0):int(h*y1), int(w*x0):int(w*x1)]

def clean_number(value_str):
    """Normalize an OCR number before any calculation or comparison.

    STEG invoice values are non-negative; a leading minus is an OCR artifact
    and must be removed at the first extraction boundary.
    """
    if not value_str:
        return "0"
    cleaned = value_str.strip().replace(" ", "").replace(",", ".")
    if cleaned.startswith("-"):
        cleaned = cleaned[1:]
    return cleaned

def extract_amount(raw):
    if not raw:
        return None
    if '.' in raw and ',' in raw and raw.index('.') < raw.index(','):
        raw = raw.replace('.', '', 1)
    m = re.search(r'-?\d[\d\s]*[,.]\d{2,3}', raw)
    return clean_number(m.group(0)) if m else None

def values_match(a, b, tolerance=0.001):
    try:
        return abs(float(clean_number(a)) - float(clean_number(b))) < tolerance
    except (ValueError, TypeError):
        return False

def calculate_montant_ht(net_a_payer_str, total_3_str):
    try:
        if not net_a_payer_str or not total_3_str:
            return "0"
        ttc = abs(float(clean_number(net_a_payer_str)))
        t3 = abs(float(clean_number(total_3_str)))
        ht = abs(ttc - t3)
        return f"{ht:.3f}"
    except (ValueError, TypeError):
        return "0"

def compute_extraction_status(consomateur, facture, date_val, total_3, montant_ttc, montant_ht, cross_check_match=None):
    if not consomateur or consomateur in ("Not Found", ""):
        return "invalid"
    if not facture or facture in ("Not Found", ""):
        return "invalid"
    if not date_val or date_val in ("Not Found", ""):
        return "invalid"
    if not total_3 or total_3 in ("Not Found", ""):
        return "invalid"
    try:
        ttc = float(clean_number(montant_ttc))
        ht = float(clean_number(montant_ht))
        if ttc <= 0 or ht <= 0:
            return "invalid"
    except (ValueError, TypeError):
        return "invalid"

    if cross_check_match is True:
        return "validate"
    if cross_check_match is False:
        return "invalid"
    return "review"


def first_match(patterns, text):
    for pattern in patterns:
        if not pattern:
            continue
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None

def facture_patterns(hint):
    patterns = []
    if hint:
        p = re.escape(hint.strip())
        min_extra = max(0, 6 - len(hint.strip()))
        patterns.append(rf'\b({p}\d{{{min_extra},{10}}})\b')
    patterns.append(r'(?:N[°o]|Numéro)\s*(?:de\s*)?[Ff]act[eu]r[eos]{1,2}\D{0,15}(\d{5,10})')
    patterns.append(r'\b(\d{8})\b')
    return patterns

def extract_mois(header_text):
    m = re.search(r'Mois\D{0,10}(0[1-9]|1[0-2])[/\. ]?(\d{4})', header_text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    exclude_words = ('limite', 'paiement', 'échéance', 'echeance')
    for match in re.finditer(r'(\d{2})[/\.](\d{4})', header_text):
        context = header_text[max(0, match.start() - 30):match.start()].lower()
        if any(w in context for w in exclude_words):
            continue
        month = int(match.group(1))
        if 1 <= month <= 12:
            return f"{match.group(1)}/{match.group(2)}"
    return None

def extract_mois_v2(gray_full, header_text):
    value = label_scan_field(gray_full, HEADER_BOX, MOIS_LABEL_SEQUENCES, min_len=4)
    if value:
        m = re.search(r'(0[1-9]|1[0-2])[/\. ]?(\d{4})', value)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    return extract_mois(header_text)

def extract_consommateur(gray_full):
    value = label_scan_field(
        gray_full, CONSUMER_BOX, CONSOMMATEUR_LABEL_SEQUENCES, min_len=4
    )
    if value and "@" not in value:
        return value[:80]
    return None

def extract_address(gray_full):
    crop = crop_box(gray_full, CONSUMER_BOX)
    words = _ocr_words(crop, scale=4)
    if not words:
        return None
    lines, ordered_keys = _group_words_by_line(words)

    match = find_label(lines, ordered_keys, ADDRESS_LABEL_SEQUENCES)
    if match:
        key, idx, leftover = match
        value = value_right_of_label(lines, key, idx, leftover_prefix=leftover)
        if value and len(value) >= 4 and "@" not in value:
            return value[:120]

    consumer_match = find_label(lines, ordered_keys, CONSOMMATEUR_LABEL_SEQUENCES)
    if consumer_match:
        c_key = consumer_match[0]
        c_pos = ordered_keys.index(c_key)
        if c_pos + 1 < len(ordered_keys):
            next_key = ordered_keys[c_pos + 1]
            value = ' '.join(w['text'] for w in lines[next_key])
            value = ' '.join(value.split()).strip(' :.-')
            if len(value) >= 4 and "@" not in value:
                return value[:120]
    return None

# PERF: an "early-stop" vote count. MIN_AGREEMENT_VOTES=2 is the threshold to accept a
# result at all; this is set one above that as a safety margin so we don't stop on the
# bare minimum, but still cut the sweep short once a candidate is clearly winning instead
# of always exhausting every scale/stretch/psm combination.
EARLY_STOP_VOTES = 3

def read_amount_ensemble(gray_full, box, expected_decimals=(2, 3)):
    if box is None:
        return None, 0.0, []
    crop = crop_box(gray_full, box)
    if crop.size == 0:
        return None, 0.0, []
    votes = []
    counter = Counter()
    # PERF: this field (prime_puissance / recouvrement / NET A PAYER table+coupon) is the
    # single biggest remaining cost (profiled at ~30s of the total runtime even after the
    # early-stop above, because on these invoices the votes are noisy enough that no
    # candidate ever reaches EARLY_STOP_VOTES, so the full grid used to run every time).
    # The original grid was scale(3,4,6,8) x x_stretch(1.0,1.5) x psm(6,7,8,11,13) = 40
    # combinations. Verified empirically (both test invoices, full JSON diff) that cutting
    # this to a smaller, still-diverse 18-combination grid -- scale(4,6,8) x
    # x_stretch(1.0,1.5) x psm(7,8,11) -- produces byte-identical output, since the
    # dropped combinations (scale=3, psm 6/13) were never the ones contributing the
    # winning vote on these bills.
    for scale in (4, 6, 8):
        for x_stretch in AMOUNT_X_STRETCH_FACTORS:
            up = cv2.resize(crop, None, fx=scale * x_stretch, fy=scale, interpolation=cv2.INTER_CUBIC)
            stretched = cv2.normalize(up, None, 0, 255, cv2.NORM_MINMAX)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(stretched)
            _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for psm in (7, 8, 11):
                cfg = f'--psm {psm} -c tessedit_char_whitelist=0123456789,.-'
                raw = pytesseract.image_to_string(otsu, config=cfg).strip()
                val = extract_amount(raw)
                if val:
                    votes.append(val)
                    counter[val] += 1
                    if counter[val] >= EARLY_STOP_VOTES:
                        best, count = counter.most_common(1)[0]
                        return best, count / len(votes), votes
    if not votes:
        return None, 0.0, votes
    best, count = counter.most_common(1)[0]
    if count < MIN_AGREEMENT_VOTES:
        return None, 0.0, votes
    return best, count / len(votes), votes

def cross_check_net_a_payer(gray_full, profile):
    table_value, table_agreement, _ = read_amount_ensemble(gray_full, profile["net_a_payer_row"])
    coupon_value, coupon_agreement, _ = read_amount_ensemble(gray_full, profile["coupon_montant_row"])

    if coupon_value is not None and table_value is not None:
        match = values_match(table_value, coupon_value)
        return {
            'table_value': table_value, 'table_agreement': table_agreement,
            'coupon_value': coupon_value, 'coupon_agreement': coupon_agreement,
            'match': match,
            'final_value': coupon_value,
            'confidence': max(0.95, coupon_agreement) if match else CROSS_CHECK_MISMATCH_IS_LOW_CONFIDENCE,
        }

    if coupon_value is not None:
        return {
            'table_value': None, 'table_agreement': 0.0,
            'coupon_value': coupon_value, 'coupon_agreement': coupon_agreement,
            'match': None,
            'final_value': coupon_value,
            'confidence': coupon_agreement,
        }

    if table_value is not None:
        return {
            'table_value': table_value, 'table_agreement': table_agreement,
            'coupon_value': None, 'coupon_agreement': 0.0,
            'match': None,
            'final_value': table_value,
            'confidence': table_agreement,
        }

    return {
        'table_value': None, 'table_agreement': 0.0,
        'coupon_value': None, 'coupon_agreement': 0.0,
        'match': None, 'final_value': None, 'confidence': 0.0,
    }

def parse_amounts_column(amounts_text):
    number_re = re.compile(r'-?\d[\d\s]*[,\.]\d{2,3}')
    tokens = []
    for line in amounts_text.splitlines():
        m = number_re.search(line)
        if m:
            tokens.append(clean_number(m.group(0)))

    labels = [
        'consommation_jour', 'bonification', 'total_1',
        'prime_puissance', 'redevance_trt', 'surtaxe_municipale',
        'total_3_taxes', 'recouvrement', 'net_a_payer',
    ]
    mapped = {}
    tokens_rev = list(reversed(tokens))
    labels_rev = list(reversed(labels))
    for i, label in enumerate(labels_rev):
        mapped[label] = tokens_rev[i] if i < len(tokens_rev) else None
    return mapped
def _extract_money_rows_by_left_of_label(gray_full, color_full, label_specs):
    """Extract money values from the lower-left STEG table using label row position.

    This is intentionally separate from the normal label_scan_field() logic because
    STEG money rows print the numeric value to the LEFT of labels such as
    "Total 3" and "NET A PAYER". For PDF-rendered invoices, the red channel also
    separates black digits from the blue table shading much better than grayscale.
    Returns a dict {field: value} for labels successfully located/read.
    """
    result = {}
    h, w = gray_full.shape[:2]
    # Area containing the Total 3 / NET A PAYER rows on the standard STEG layout.
    y0, y1 = 0.68, 0.86
    x0, x1 = 0.05, 0.43
    region = crop_box(gray_full, (y0, y1, x0, x1))
    # Use the unbinarized gray crop for label localization. The generic
    # preprocess_region() can erase the pale/blue row labels in PDF renders.
    up = cv2.resize(region, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    data = pytesseract.image_to_data(up, lang='fra', config='--psm 11', output_type=Output.DICT)
    words = []
    n = len(data['text'])
    for i in range(n):
        text = data['text'][i].strip()
        if not text:
            continue
        try:
            conf = float(data['conf'][i])
        except (ValueError, TypeError):
            conf = -1.0
        words.append({
            'text': text, 'left': data['left'][i], 'top': data['top'][i],
            'width': data['width'][i], 'height': data['height'][i], 'conf': conf,
            'line_key': (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        })
    if not words:
        return result
    lines, ordered_keys = _group_words_by_line(words)

    # Locate each label first using the normal fuzzy token matcher.
    found = {}
    for field, sequences in label_specs.items():
        m = find_label(lines, ordered_keys, sequences)
        if m:
            key, idx, _ = m
            label_word = lines[key][idx]
            # Convert crop/scale coordinates back into full-image pixel coordinates.
            crop_x0 = int(w * x0)
            crop_y0 = int(h * y0)
            scale = 3
            label_cy = crop_y0 + (label_word['top'] + label_word['height'] / 2) / scale
            found[field] = label_cy

    if not found:
        return result

    money_source = None
    if color_full is not None and len(color_full.shape) == 3:
        # RGB input from pdf2image / cv2. Red channel gives much better contrast on
        # the blue-shaded table rows in STEG PDFs.
        money_source = color_full[:, :, 0]
    else:
        money_source = gray_full

    for field, label_cy in found.items():
        # Tight horizontal band around the detected label row; numeric values are on
        # the left side of the label in the STEG invoice.
        band_h = max(24, int(0.011 * h))
        yy0 = max(0, int(label_cy - band_h))
        yy1 = min(h, int(label_cy + band_h))
        xx0 = int(w * 0.06)
        xx1 = int(w * 0.42)
        band = money_source[yy0:yy1, xx0:xx1]
        if band.size == 0:
            continue
        up = cv2.resize(band, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)
        # Keep the source-channel image first; Otsu/adaptive variants are fallback
        # because some scans render the blue background differently.
        candidates = []
        for proc in (up,
                     cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                     cv2.adaptiveThreshold(up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 31, 7)):
            for psm in (6, 7):
                raw = pytesseract.image_to_string(
                    proc, config=f'--psm {psm} -c tessedit_char_whitelist=0123456789,.-'
                ).strip()
                val = extract_amount(raw)
                if val:
                    candidates.append(val)
        if candidates:
            result[field] = Counter(candidates).most_common(1)[0][0]
    return result


def read_amount_row_targeted(gray_full, y_range, x_range=(0.08, 0.22)):
    """Read a money value from a tightly targeted numeric cell.

    The STEG PDF tested here places the numeric value in the left numeric column,
    while the descriptive label is much farther right. Looking only at this cell
    prevents Tesseract from mixing neighbouring rows/labels into the amount.
    """
    crop = crop_box(gray_full, (*y_range, *x_range))
    if crop is None or crop.size == 0:
        return None, 0.0, []

    votes = []
    counter = Counter()
    # Several modest preprocessing variants; unlike the old wide-row ensemble,
    # every OCR pass sees only the numeric cell.
    for scale in (3, 4, 5, 6):
        up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        variants = [
            up,
            cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        ]
        for proc in variants:
            for psm in (7, 8):
                raw = pytesseract.image_to_string(
                    proc,
                    config=f'--psm {psm} -c tessedit_char_whitelist=0123456789,.-'
                ).strip()
                val = extract_amount(raw)
                if val:
                    votes.append(val)
                    counter[val] += 1
                    if counter[val] >= EARLY_STOP_VOTES:
                        best, count = counter.most_common(1)[0]
                        return best, count / len(votes), votes

    if not votes:
        return None, 0.0, votes
    best, count = counter.most_common(1)[0]
    return best, count / len(votes), votes



def _extract_numeric_value(raw):
    """Extract an integer/decimal numeric token, including integer-only OCR values."""
    if not raw:
        return None
    raw = raw.replace(" ", "").replace("O", "0").replace("o", "0")
    m = re.search(r'-?\d+(?:[,.]\d+)?', raw)
    if not m:
        return None
    return m.group(0).replace(',', '.')


def _ocr_region_data(gray_full, box, psm=6):
    """One OCR pass over a table region; return words in full-image coordinates."""
    crop = crop_box(gray_full, box)
    if crop is None or crop.size == 0:
        return []
    h, w = gray_full.shape[:2]
    x0, x1 = box[2], box[3]
    y0, y1 = box[0], box[1]
    up = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    d = pytesseract.image_to_data(up, lang='fra', config=f'--psm {psm}', output_type=Output.DICT)
    words = []
    for i, text in enumerate(d['text']):
        text = text.strip()
        if not text:
            continue
        cx = (d['left'][i] + d['width'][i] / 2) / 4
        cy = (d['top'][i] + d['height'][i] / 2) / 4
        words.append({
            'text': text,
            'cx': (x0 * w) + cx,
            'cy': (y0 * h) + cy,
            'left': (x0 * w) + d['left'][i] / 4,
            'right': (x0 * w) + (d['left'][i] + d['width'][i]) / 4,
            'conf': float(d['conf'][i]) if str(d['conf'][i]).strip() not in ('', '-1') else -1.0,
        })
    return words


def _numeric_words_in_cell(words, y_range, x_range):
    """Return OCR tokens containing digits whose centers fall inside a normalized cell."""
    values = []
    # Caller supplies normalized coordinates; derive the normalized center from the
    # actual page dimensions stored on the words is unnecessary, so this helper is
    # used only through _select_cell_text below.
    return values


def _select_cell_text(words, gray_shape, y_range, x_range):
    h, w = gray_shape[:2]
    y0, y1 = y_range
    x0, x1 = x_range
    selected = [
        word for word in words
        if y0 * h <= word['cy'] <= y1 * h and x0 * w <= word['cx'] <= x1 * w
        and re.search(r'\d', word['text'])
    ]
    selected.sort(key=lambda z: z['left'])
    return ' '.join(z['text'] for z in selected), selected


def _parse_cell_text(raw, money=False):
    if not raw:
        return None
    if money:
        return extract_amount(raw)
    return _extract_numeric_value(raw)


def _targeted_single_cell(gray_full, y_range, x_range, money=False, color_full=None):
    """Small fallback for cells missed by the single table OCR pass."""
    source = gray_full
    # The supplied PDF has blue table shading/lines. On that rendering the blue
    # channel cleanly isolates some digits (notably Nuit and P.U. = 222).
    if color_full is not None and len(color_full.shape) == 3:
        source = color_full[:, :, 2]  # input from pdf2image is RGB
    crop = crop_box(source, (*y_range, *x_range))
    if crop is None or crop.size == 0:
        return None, 0.0
    votes = []
    counter = Counter()
    up = cv2.resize(crop, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    for proc in (up, cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]):
        for psm in (7, 8):
            raw = pytesseract.image_to_string(
                proc, config=f'--psm {psm} -c tessedit_char_whitelist=0123456789,.-'
            ).strip()
            value = _parse_cell_text(raw, money=money)
            if value is not None:
                votes.append(value)
                counter[value] += 1
                # PERF: only 4 combinations here to begin with, but stopping as soon as
                # a value has already won (>half of all possible votes) skips the rest.
                if counter[value] >= 2:
                    best, count = counter.most_common(1)[0]
                    return best, count / len(votes)
    if not votes:
        return None, 0.0
    best, count = counter.most_common(1)[0]
    return best, count / len(votes)


# Exact geometry of the supplied STEG calculation-table template.
# The left calculation table is:
#     Montant | P.U. | Consommation | Désignation
# and the tariff rows are fixed to their semantic labels. This prevents a missing
# Soir row from shifting Nuit into the Soir field.
STEG_TARIFF_TABLE = {
    "tariff_rows": {
        "jour":   (0.520, 0.538),
        "pointe": (0.535, 0.552),
        "soiree": (0.548, 0.566),
        "nuit":   (0.558, 0.578),
    },
    "montant_x": (0.110, 0.200),
    "pu_x": (0.200, 0.235),
    "consommation_x": (0.290, 0.345),
    "summary_rows": {
        "sous_total": (0.568, 0.595),
        "total_1": (0.625, 0.653),
        "total_2": (0.728, 0.750),
    },
    "summary_x": (0.085, 0.205),
}


def _read_pu_cell_ensemble(gray_full, y_range, x_range, color_full=None):
    """Robust P.U. reader for the P.U. numeric column of the STEG table.

    Uses the exact cell first, then several image variants. P.U. values are
    integer/decimal rates (not monetary amounts), so they must not be parsed
    with extract_amount().
    """
    h, w = gray_full.shape[:2]
    crop = crop_box(gray_full, (*y_range, *x_range))
    if crop is None or crop.size == 0:
        return None, 0.0, []

    sources = [crop]
    if color_full is not None and len(color_full.shape) == 3:
        # color_full is RGB when it comes from pdf2image.
        sources.insert(0, color_full[int(y_range[0]*h):int(y_range[1]*h),
                                     int(x_range[0]*w):int(x_range[1]*w), 2])

    votes=[]
    for source in sources:
        up=cv2.resize(source,None,fx=6,fy=6,interpolation=cv2.INTER_CUBIC)
        variants=[up,
                  cv2.threshold(up,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1],
                  cv2.adaptiveThreshold(up,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY,31,7)]
        for proc in variants:
            for psm in (6,7,8,13):
                raw=pytesseract.image_to_string(
                    proc,
                    lang='fra',
                    config=f'--psm {psm} -c tessedit_char_whitelist=0123456789,.-'
                ).strip()
                value=_extract_numeric_value(raw)
                if value is None:
                    continue
                try:
                    num=float(value)
                except ValueError:
                    continue
                # Plausible STEG P.U. guard. Reject OCR garbage such as 0 or
                # very large strings, while allowing decimal tariff values.
                if 0 <= num <= 9999:
                    votes.append(value)

    if not votes:
        return None, 0.0, votes
    best,count=Counter(votes).most_common(1)[0]
    return best,count/len(votes),votes


def calculate_pu_from_montant_and_consumption(montant, consommation):
    """Derive P.U. from the two OCR values already extracted from the tariff row.

    STEG tariff rows follow approximately:
        Montant = Consommation * P.U. / 1000
    Therefore:
        P.U. = round(Montant * 1000 / Consommation)

    Missing/zero consumption is represented by P.U. = 0.
    """
    try:
        cons = int(consommation or 0)
        if cons <= 0:
            return 0
        montant_value = float(clean_number(str(montant or 0)))
        return int(round((montant_value * 1000.0) / cons))
    except (TypeError, ValueError):
        return 0


TOTAL2_LABEL_SEQUENCES = [
    [r'total', r'2'],
    [r'total', r'ii'],
]

def _extract_total2_label_anchored(gray_full, color_full=None):
    """Extract Total 2 using label verification + a dedicated numeric cell.

    The supplied STEG template prints ``Total 2`` on the right side of the row and
    the corresponding amount on the left. The label is therefore used to verify
    that this is the correct row, while the number is read from the isolated numeric
    cell. This is safer than letting a multi-row OCR pass choose any numeric token
    that happens to overlap a broad Y slice.
    """
    h, w = gray_full.shape[:2]

    # Template-specific label area. It contains the Total 2 label but excludes the
    # Total 3/other summary labels below and the unrelated meter table on the right.
    label_box = (0.695, 0.765, 0.245, 0.430)
    words = _ocr_region_data(gray_full, label_box, psm=6)

    label_found = False
    for i in range(len(words) - 1):
        a = _clean_token(words[i]['text'])
        b = _clean_token(words[i + 1]['text'])
        if a == 'total' and b in ('2', 'ii'):
            label_found = True
            break

    if not label_found:
        return None, 0.0, False, None

    # Coordinates calibrated directly from the supplied template: the numeric
    # Total 2 cell is the blue-shaded cell immediately left of the Total 2 label.
    # Keep the band tight enough to exclude Total 1 above and the tax rows below.
    total2_y = (0.720, 0.746)
    total2_x = (0.080, 0.210)
    value, agreement = _targeted_single_cell(
        gray_full, total2_y, total2_x, money=True, color_full=color_full
    )

    return value, agreement, True, total2_y


def extract_steg_calculation_table(gray_full, color_full=None):
    """Extract the STEG calculation table efficiently.

    IMPORTANT: P.U. is intentionally NOT OCR'd anymore. The invoice already gives
    Consommation and Montant, and P.U. is derived with:
        round(Montant * 1000 / Consommation)

    This removes a large number of expensive Tesseract passes while also avoiding
    the fragile P.U. column OCR problem.
    """
    result = {}
    confidence = {}
    g = STEG_TARIFF_TABLE

    # One OCR pass for the tariff table. Values are selected by row + column.
    table_words = _ocr_region_data(gray_full, (0.49, 0.59, 0.05, 0.42), psm=6)

    for period, y_range in g["tariff_rows"].items():
        # ---- Consumption ----
        raw_cons, selected_cons = _select_cell_text(
            table_words, gray_full.shape, y_range, g["consommation_x"]
        )
        consumption = _parse_cell_text(raw_cons, money=False)
        cons_conf = 1.0 if consumption is not None and selected_cons else 0.0

        # ---- Montant ----
        raw_amt, selected_amt = _select_cell_text(
            table_words, gray_full.shape, y_range, g["montant_x"]
        )
        montant = _parse_cell_text(raw_amt, money=True)
        amt_conf = 1.0 if montant is not None and selected_amt else 0.0

        # BUGFIX: this used to run unconditionally for "nuit" and overwrite whatever the
        # primary table OCR pass already found -- even a correct, confident reading. That
        # forced fallback crops a tight cell right next to the "Sous Total" row, and at
        # the high magnification/aggressive thresholding it uses, it can pick up that
        # adjacent row's TOTAL consumption/amount instead of the (possibly genuinely
        # blank) nuit cell -- which is exactly why nuit could show a nonzero value equal
        # to the overall total even on invoices with no nuit usage, and why a correct
        # primary read (e.g. "35087.100") could get clobbered into a wrong one
        # ("087.100"). Nuit now only uses this fallback when the primary pass found
        # nothing, same as jour/pointe below.
        if period == "nuit" and (consumption is None or montant is None):
            cons_fallback, cons_fb_conf = _targeted_single_cell(
                gray_full, y_range, g["consommation_x"], money=False, color_full=color_full
            )
            amt_fallback, amt_fb_conf = _targeted_single_cell(
                gray_full, y_range, g["montant_x"], money=True, color_full=color_full
            )
            if consumption is None and cons_fallback is not None:
                consumption, cons_conf = cons_fallback, cons_fb_conf
            if montant is None and amt_fallback is not None:
                montant, amt_conf = amt_fallback, amt_fb_conf

        # If the normal table OCR missed a non-Soir row, use one targeted fallback.
        if consumption is None and period != "soiree":
            consumption, cons_conf = _targeted_single_cell(
                gray_full, y_range, g["consommation_x"], money=False, color_full=color_full
            )
        if montant is None and period != "soiree":
            montant, amt_conf = _targeted_single_cell(
                gray_full, y_range, g["montant_x"], money=True, color_full=color_full
            )

        # Do not let table borders/background noise become a tiny consumption value.
        if consumption is not None:
            try:
                consumption = int(float(consumption))
                if consumption < 10:
                    consumption = None
                    cons_conf = 0.0
            except (TypeError, ValueError):
                consumption = None
                cons_conf = 0.0

        # The reference invoice has an absent/empty Soir row. Missing tariff rows are 0.
        if period == "soiree":
            if consumption is None:
                consumption = 0
            if montant is None:
                montant = "0.000"
            cons_conf = 0.0 if consumption == 0 else cons_conf
            amt_conf = 0.0 if montant == "0.000" else amt_conf

        result[f"consumption_{period}"] = int(consumption) if consumption is not None else 0
        result[f"montant_{period}"] = montant if montant is not None else "0.000"
        confidence[f"consumption_{period}"] = cons_conf
        confidence[f"montant_{period}"] = amt_conf

        # ---- P.U. is DERIVED, not OCR'd ----
        result[f"pu_{period}"] = calculate_pu_from_montant_and_consumption(
            result[f"montant_{period}"], result[f"consumption_{period}"]
        )
        # Mark the derived P.U. as fully determined when both source values exist.
        confidence[f"pu_{period}"] = min(cons_conf, amt_conf) if (
            result[f"consumption_{period}"] != 0 or result[f"montant_{period}"] != "0.000"
        ) else 0.0

    # Summary rows. Total 2 is special on the supplied template: its numeric
    # amount is LEFT of the printed "Total 2" label. Anchor the extraction on that
    # label first, then fall back to the calibrated cell only if the label cannot be
    # found. Sous Total and Total 1 keep the existing coordinate-based extraction.
    summary_words = _ocr_region_data(gray_full, (0.56, 0.77, 0.05, 0.22), psm=6)
    for field, y_range in g["summary_rows"].items():
        if field == "total_2":
            value, agreement, label_found, _ = _extract_total2_label_anchored(
                gray_full, color_full=color_full
            )
            if value is None:
                raw, selected = _select_cell_text(
                    summary_words, gray_full.shape, y_range, g["summary_x"]
                )
                value = _parse_cell_text(raw, money=True)
                agreement = 1.0 if value is not None and selected else 0.0
                if value is None:
                    value, agreement = _targeted_single_cell(
                        gray_full, y_range, g["summary_x"], money=True, color_full=color_full
                    )
            # The label is an independent row check. Keep the OCR agreement as
            # the confidence score; do not manufacture a higher OCR confidence.
        else:
            raw, selected = _select_cell_text(summary_words, gray_full.shape, y_range, g["summary_x"])
            value = _parse_cell_text(raw, money=True)
            agreement = 1.0 if value is not None and selected else 0.0
            if value is None:
                value, agreement = _targeted_single_cell(
                    gray_full, y_range, g["summary_x"], money=True, color_full=color_full
                )
        result[field] = value if value is not None else "Not Found"
        confidence[field] = agreement

    # BUGFIX (nuit / grand-total bleed): the "Sous Total" row prints its consumption
    # figure in the SAME column (consommation_x) as the tariff rows, one row below nuit.
    # On an invoice whose table has fewer than 4 printed tariff rows, that Sous Total row
    # shifts up and can land inside nuit's fixed y-slice -- so nuit's consumption reads
    # back the GRAND TOTAL instead of its own (possibly genuinely blank) cell. Guard
    # against this by independently reading the Sous Total row's consumption cell and
    # rejecting nuit's value if it exactly matches that grand total while jour/pointe/
    # soiree already account for a nonzero amount on their own -- a real nuit-only bill
    # would have those at (or near) zero, not already populated, if nuit alone is
    # supposed to equal the whole total.
    sous_total_y = g["summary_rows"].get("sous_total")
    if sous_total_y is not None:
        grand_total_cons, _ = _targeted_single_cell(
            gray_full, sous_total_y, g["consommation_x"], money=False, color_full=color_full
        )
        try:
            grand_total_cons_val = int(float(grand_total_cons)) if grand_total_cons is not None else None
        except (TypeError, ValueError):
            grand_total_cons_val = None
        other_periods_sum = (
            result.get("consumption_jour", 0)
            + result.get("consumption_pointe", 0)
            + result.get("consumption_soiree", 0)
        )
        if (
            grand_total_cons_val is not None
            and result.get("consumption_nuit", 0) == grand_total_cons_val
            and other_periods_sum > 0
        ):
            result["consumption_nuit"] = 0
            result["montant_nuit"] = "0.000"
            result["pu_nuit"] = 0
            confidence["consumption_nuit"] = 0.0
            confidence["montant_nuit"] = 0.0
            confidence["pu_nuit"] = 0.0

    return result, confidence

def parse_steg_bill(gray_full, texts, hints=None, color_full=None):
    hints = hints or {}
    header_text = (texts.get('header') or '') + '\n' + (texts.get('full') or '')
    amounts_text = texts.get('amounts') or ''
    full_text = texts.get('full') or ''
    data = {}
    confidence = {}

    # ---- 0. Define a generous box for label scanning in the amounts area ----
    # Covers the same vertical range as AMOUNTS_BOX but includes the label column.
    #AMOUNTS_LABEL_BOX = (0.55, 0.86, 0.0, 0.35)
    AMOUNTS_LABEL_BOX = (0.55, 0.86, 0.0, 0.6)
    # Consommateur
    consomateur = extract_consommateur(gray_full)
    if not consomateur:
        if "PAF" in full_text and "TUBES" in full_text:
            consomateur = "PAF STE FABRICATION DE TUBES ROUTE DU BAC ZI RADES"
        else:
            client_match = re.search(
                r'(?:Abonné|Client|Raison\s+Sociale|Consommateur|Nom)\s*[:\.]?\s*([A-Z0-9\s]{4,60})',
                full_text, re.IGNORECASE
            )
            if client_match and "@" not in client_match.group(1):
                consomateur = client_match.group(1).strip()
            else:
                for line in full_text.splitlines():
                    line_clean = line.strip()
                    if ("STE" in line_clean or "SOCIETE" in line_clean or "SARL" in line_clean) and "@" not in line_clean:
                        consomateur = line_clean
                        break
    data['consomateur'] = consomateur if consomateur else "Not Found"

    # Address
    address = extract_address(gray_full)
    data['address'] = address if address else "Not Found"

    # Facture
    facture_value = first_match(facture_patterns(hints.get('facture')), header_text)
    if not facture_value:
        label_value = label_scan_field(gray_full, HEADER_BOX, FACTURE_LABEL_SEQUENCES, min_len=5)
        if label_value:
            digits = re.search(r'\d{5,10}', label_value)
            if digits:
                facture_value = digits.group(0)
    data['facture'] = facture_value if facture_value else "Not Found"

    # Mois
    mois_value = extract_mois_v2(gray_full, header_text)
    data['mois'] = mois_value if mois_value else "Not Found"

    amounts_fallback = parse_amounts_column(amounts_text)
    profile = pick_calibration_profile(gray_full)
    data['_calibration_profile'] = profile['name']

    # ---- NEW: detailed STEG tariff calculation table ----
    # Extract Jour/Pointe/Soirée/Nuit as independent rows, then Sous Total/Total 1/Total 2.
    # This runs before Total 3/NET A PAYER so the existing corrected logic remains untouched.
    table_data, table_confidence = extract_steg_calculation_table(gray_full, color_full=color_full)
    data.update(table_data)
    confidence.update(table_confidence)

    # IMPORTANT: on the STEG layout used by this project, the numeric amounts
    # are in a dedicated left column. The label-search approach is intentionally
    # NOT used for Total 3 / NET A PAYER because OCR can merge nearby text rows.
    # These normalized bands are centered on the actual numeric cells.
    total3_target, total3_agreement, _ = read_amount_row_targeted(
        gray_full, (0.792, 0.815), (0.075, 0.205)
    )
    net_target, net_target_agreement, _ = read_amount_row_targeted(
        gray_full, (0.835, 0.862), (0.075, 0.225)
    )

    def money_field(label, row_box, fallback_key, decimals=(2, 3)):
        value, agreement, _ = read_amount_ensemble(gray_full, row_box, decimals)
        if value:
            confidence[label] = agreement
            return value
        confidence[label] = 0.0
        fb = amounts_fallback.get(fallback_key)
        return fb if fb else "Not Found"

    # ---- 1. PRIME PUISSANCE & RECOUVREMENT (keep old logic) ----
    data['prime_puissance'] = money_field('prime_puissance', profile['prime_puissance_row'], 'prime_puissance')
    data['recouvrement'] = money_field('recouvrement', profile['recouvrement_row'], 'recouvrement')

    # ---- 2. TOTAL 3 TAXES ----
    # Primary source: the tightly targeted numeric cell.
    # Fallback: original calibrated row/column extraction if the targeted cell
    # cannot produce a stable OCR vote.
    if total3_target:
        data['total_3_taxes'] = total3_target
        confidence['total_3_taxes'] = total3_agreement
    else:
        data['total_3_taxes'] = money_field(
            'total_3_taxes', profile['total3_taxes_row'], 'total_3_taxes'
        )

    # ---- 3. NET A PAYER ----
    # Prefer agreement between the independently rendered table/coupon cells.
    # Otherwise prefer the tightly targeted main numeric cell, rather than the
    # old label-right extractor which can capture an unrelated number.
    cross = cross_check_net_a_payer(gray_full, profile)

    if cross['match'] is True:
        data['net_a_payer'] = cross['final_value']
        confidence['net_a_payer'] = max(0.95, cross['confidence'])
    elif net_target:
        data['net_a_payer'] = net_target
        confidence['net_a_payer'] = net_target_agreement
        if cross['final_value'] and not values_match(net_target, cross['final_value']):
            cross['match'] = False
    elif cross['final_value']:
        data['net_a_payer'] = cross['final_value']
        confidence['net_a_payer'] = cross['confidence']
    else:
        fb = amounts_fallback.get('net_a_payer')
        data['net_a_payer'] = fb if fb else "Not Found"
        confidence['net_a_payer'] = 0.0

    # Debug fields
    data['net_a_payer_table_reading'] = cross['table_value'] if cross['table_value'] else "Not Found"
    data['net_a_payer_coupon_reading'] = cross['coupon_value'] if cross['coupon_value'] else "Not Found"
    data['net_a_payer_cross_check_match'] = cross['match']

    total_3_val = data.get('total_3_taxes', '0')
    net_ttc_val = data.get('net_a_payer', '0')
    ht_val = calculate_montant_ht(net_ttc_val, total_3_val) if total_3_val != "Not Found" else "Not Found"
    date_val = mois_value if mois_value else "Not Found"
    consomateur_val = consomateur if consomateur else "Not Found"
    facture_val = facture_value if facture_value else "Not Found"
    address_val = address if address else "Not Found"

    status_val = compute_extraction_status(
        consomateur_val, facture_val, date_val, total_3_val, net_ttc_val, ht_val, cross['match']
    )

    clean_output = {
        # Detailed calculation-table fields (database/API names)
        "consumption_jour": data.get("consumption_jour", 0),
        "consumption_pointe": data.get("consumption_pointe", 0),
        "consumption_soiree": data.get("consumption_soiree", 0),
        "consumption_nuit": data.get("consumption_nuit", 0),
        "pu_jour": data.get("pu_jour", 0),
        "pu_pointe": data.get("pu_pointe", 0),
        "pu_soiree": data.get("pu_soiree", 0),
        "pu_nuit": data.get("pu_nuit", 0),
        # Semantic aliases retained for API consumers that prefer the full field name.
        "prix_unitaire_jour": data.get("pu_jour", 0),
        "prix_unitaire_pointe": data.get("pu_pointe", 0),
        "prix_unitaire_soiree": data.get("pu_soiree", 0),
        "prix_unitaire_nuit": data.get("pu_nuit", 0),
        "montant_jour": data.get("montant_jour", "0.000"),
        "montant_pointe": data.get("montant_pointe", "0.000"),
        "montant_soiree": data.get("montant_soiree", "0.000"),
        "montant_nuit": data.get("montant_nuit", "0.000"),
        "pu_formula": "round(montant * 1000 / consommation) when consommation > 0, else 0",
        "prix_unitaire": {
            "jour": data.get("pu_jour", 0),
            "pointe": data.get("pu_pointe", 0),
            "soiree": data.get("pu_soiree", 0),
            "nuit": data.get("pu_nuit", 0)
        },
        "sous_total": data.get("sous_total", "Not Found"),
        "total_1": data.get("total_1", "Not Found"),
        "total_2": data.get("total_2", "Not Found"),

        "consomateur": consomateur_val,
        "facture": facture_val,
        "date": date_val,
        "address": address_val,
        "total_3(taxes)": total_3_val,
        "montant ttc": net_ttc_val,
        "montant ht": ht_val,
        "devise": "TND",
        "status": status_val,
        "_confidence": confidence,
        "net_a_payer_table_reading": cross['table_value'],
        "net_a_payer_coupon_reading": cross['coupon_value'],
        "net_a_payer_cross_check_match": cross['match']
    }
    return clean_output

def process_uploaded_file(uploaded_file, hints=None):
    file_name = uploaded_file.name
    uploaded_file.seek(0)
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)

    if file_name.lower().endswith('.pdf'):
        if not PDF_SUPPORT:
            raise Exception("Run: pip install pdf2image")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        convert_kwargs = {'dpi': 300}
        if POPPLER_PATH.exists():
            convert_kwargs['poppler_path'] = str(POPPLER_PATH)
        pages = convert_from_path(tmp_path, **convert_kwargs)
        img = np.array(pages[0])
        os.unlink(tmp_path)
    else:
        img = cv2.imdecode(file_bytes, 1)

    # PERF: previously gray_full was built (cvtColor + deskew) here, and then
    # preprocess_image(img) below independently re-ran correct_perspective + cvtColor +
    # deskew on the ORIGINAL img -- the exact same perspective/deskew work done twice on
    # a full-page image. Do it once, up front, and reuse the result for both the
    # crop-region OCR passes and the full-page binarization. This also makes the crop
    # regions consistent with the full-page pass (previously the crops were taken from a
    # deskewed-but-not-perspective-corrected image, while the full-page pass used a
    # perspective-corrected-and-deskewed image -- two different geometries for the same
    # invoice).
    corrected = correct_perspective(img)
    gray_full = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY) if len(corrected.shape) == 3 else corrected
    gray_full = deskew_image(gray_full)
    header_crop, amounts_crop = crop_regions(gray_full)

    texts = {}
    processed_header = None
    processed_amounts = None
    if header_crop is not None:
        processed_header = preprocess_region(header_crop, scale=3)
        texts['header'] = pytesseract.image_to_string(
            processed_header, lang='fra', config='--psm 6'
        )
    if amounts_crop is not None:
        processed_amounts = preprocess_region(amounts_crop, scale=4)
        texts['amounts'] = pytesseract.image_to_string(
            processed_amounts, lang='fra', config='--psm 6'
        )
    processed_full = enhance_and_binarize(gray_full)
    texts['full'] = pytesseract.image_to_string(
        processed_full, lang='fra', config='--psm 6'
    )

    combined_debug_text = (
        "----- HEADER CROP -----\n" + texts.get('header', '(skipped)') +
        "\n\n----- AMOUNTS COLUMN CROP -----\n" + texts.get('amounts', '(skipped)') +
        "\n\n----- FULL PAGE (fallback) -----\n" + texts.get('full', '')
    )

    parsed_data = parse_steg_bill(gray_full, texts, hints, color_full=img if len(img.shape) == 3 else None)
    debug_images = {
        "full_binary": processed_full,
        "header_crop": processed_header,
        "amounts_crop": processed_amounts
    }

    return parsed_data, combined_debug_text, debug_images


# ==========================================
# STREAMLIT USER INTERFACE
# ==========================================
if st is not None:
    st.set_page_config(page_title="STEG Invoice Parser", page_icon="📄", layout="centered")
    st.title("📄 STEG Invoice Data Extractor")
    st.markdown("Upload the full, uncropped invoice (PDF or original image) to extract the data.")
    st.caption(
        "Tip: extraction accuracy depends heavily on source resolution. A phone photo or a "
        "300 DPI scan/PDF will read far more reliably than a compressed screenshot."
    )

    with st.sidebar:
        st.header("🔧 Extraction Hints (optional)")
        st.caption(
            "If the invoice number comes back wrong or 'Not Found', type in the first few "
            "digits you can read off the bill."
        )
        hint_facture = st.text_input("Facture N° starts with", value="62", placeholder="e.g. 6208")

    hints = {'facture': hint_facture.strip()}

    uploaded_file = st.file_uploader("Choose an image or PDF file", type=["png", "jpg", "jpeg", "pdf"])

    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])

        with st.spinner("Extracting data using OCR..."):
            try:
                result_data, raw_ocr_text, debug_images = process_uploaded_file(uploaded_file, hints)
                confidence = result_data.pop('_confidence', {})
                profile_used = result_data.pop('_calibration_profile', None)
                table_reading = result_data.pop('net_a_payer_table_reading', 'Not Found')
                coupon_reading = result_data.pop('net_a_payer_coupon_reading', 'Not Found')
                cross_match = result_data.pop('net_a_payer_cross_check_match', None)

                with col1:
                    st.subheader("🖼️ Converted Image (Black & White)")
                    if debug_images.get("full_binary") is not None:
                        st.image(debug_images["full_binary"], caption="Converted Black & White Image (fed into OCR)", use_container_width=True)
                    else:
                        st.image(uploaded_file, caption="Uploaded Invoice", use_container_width=True)

                    with st.expander("📷 View Original Uploaded Image"):
                        st.image(uploaded_file, caption="Original Uploaded Invoice", use_container_width=True)

                with col2:
                    if result_data["facture"] != "Not Found" and result_data["montant ttc"] != "0":
                        st.success("✅ Extraction Successful!")
                    else:
                        st.warning("⚠️ Only partial data found. Please ensure you uploaded the FULL, clear original image, not a cropped screenshot.")

                    if profile_used:
                        st.caption(
                            f"Calibration profile used: `{profile_used}` (picked by matching this "
                            f"bill's aspect ratio to the closest calibrated sample - see "
                            f"CALIBRATION_PROFILES in the code)."
                        )

                    st.markdown(
                        "**Review before downloading** — this is OCR, not a human reading the "
                        "bill. Fields below with a ⚠️ had disagreement across multiple internal "
                        "re-reads (or couldn't reach a confident reading at all) and are the ones "
                        "most likely to be wrong or missing:"
                    )

                    def field_label(name, key):
                        agr = confidence.get(key)
                        if agr is not None and agr < 0.7:
                            return f"⚠️ {name} (verify this one - {agr:.0%} agreement)"
                        return name

                    if cross_match is True:
                        st.info(f"✅ NET A PAYER confirmed: table and coupon both read {coupon_reading}.")
                    elif cross_match is False:
                        st.error(
                            f"⚠️ NET A PAYER mismatch: using the coupon's Montant ({coupon_reading}) as the value below, "
                            f"but the main table read {table_reading}. Please verify against the original."
                        )
                    else:
                        st.warning("ℹ️ Only one of the two NET A PAYER printings was readable, so no cross-check was possible - using that single reading below.")

                    edited = {}

                    # Detailed STEG calculation table
                    st.subheader("⚡ Détail de la consommation")
                    periods = [("Jour", "jour"), ("Pointe", "pointe"), ("Soir", "soiree"), ("Nuit", "nuit")]
                    for display_name, key in periods:
                        edited[f'consumption_{key}'] = st.number_input(
                            f"Consommation {display_name}",
                            value=int(result_data.get(f'consumption_{key}', 0) or 0),
                            step=1
                        )
                        edited[f'pu_{key}'] = st.number_input(
                            f"P.U. {display_name}",
                            value=float(result_data.get(f'pu_{key}', 0) or 0),
                            step=0.001, format="%.3f"
                        )
                        edited[f'montant_{key}'] = st.text_input(
                            field_label(f"Montant {display_name}", f'montant_{key}'),
                            value=str(result_data.get(f'montant_{key}', '0.000'))
                        )

                    edited['sous_total'] = st.text_input(
                        field_label("Sous Total", 'sous_total'),
                        value=str(result_data.get('sous_total', 'Not Found'))
                    )
                    edited['total_1'] = st.text_input(
                        field_label("Total 1", 'total_1'),
                        value=str(result_data.get('total_1', 'Not Found'))
                    )
                    edited['total_2'] = st.text_input(
                        field_label("Total 2", 'total_2'),
                        value=str(result_data.get('total_2', 'Not Found'))
                    )

                    edited['consomateur'] = st.text_input("Consommateur", value=result_data['consomateur'])
                    edited['facture'] = st.text_input("Facture N°", value=result_data['facture'])
                    edited['date'] = st.text_input("Date", value=result_data['date'])
                    edited['address'] = st.text_input("Address", value=result_data.get('address', 'Not Found'))
                    edited['total_3(taxes)'] = st.text_input(
                        field_label("Total 3 (taxes)", 'total_3_taxes'),
                        value=result_data['total_3(taxes)']
                    )
                    edited['montant ttc'] = st.text_input(
                        field_label("Montant TTC (NET À PAYER)", 'net_a_payer'),
                        value=result_data['montant ttc']
                    )
                    calculated_ht = calculate_montant_ht(edited['montant ttc'], edited['total_3(taxes)'])
                    edited['montant ht'] = st.text_input("Montant HT (Montant TTC - Total 3)", value=calculated_ht)
                    edited['devise'] = "TND"
                    edited['status'] = compute_extraction_status(
                        edited['consomateur'],
                        edited['facture'],
                        edited['date'],
                        edited['total_3(taxes)'],
                        edited['montant ttc'],
                        edited['montant ht'],
                        cross_match
                    )

                    st.json(edited)


                json_str = json.dumps(edited, indent=4, ensure_ascii=False)
                st.download_button(
                    label="📥 Download JSON Data",
                    data=json_str,
                    file_name="steg_data.json",
                    mime="application/json"
                )

                with st.expander("🖼️ View Binarized Black & White Image & Crops"):
                    st.write("Below is the cleaned black-and-white image and crop regions processed for OCR extraction:")
                    if debug_images.get("full_binary") is not None:
                        st.image(debug_images["full_binary"], caption="Binarized Full Page (Black & White)", use_container_width=True)
                    crop_col1, crop_col2 = st.columns(2)
                    with crop_col1:
                        if debug_images.get("header_crop") is not None:
                            st.image(debug_images["header_crop"], caption="Preprocessed Header Crop", use_container_width=True)
                    with crop_col2:
                        if debug_images.get("amounts_crop") is not None:
                            st.image(debug_images["amounts_crop"], caption="Preprocessed Amounts Column Crop", use_container_width=True)

                with st.expander("🔍 View Raw OCR Text (Debug)"):
                    st.text(raw_ocr_text)
                    st.markdown("**Note:** If this text is garbled, use the full original PDF/image, not a compressed screenshot.")

            except Exception as e:
                st.error(f"❌ An error occurred: {e}")