# -*- coding: utf-8 -*-
"""OCR Flow Diagnostic Test - checks if your OCR pipeline is working"""
import sys
import os

# Force UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'back')

from pathlib import Path

print("=" * 60)
print("InvoiceFlow OCR Diagnostic Test")
print("=" * 60)

# Test 1: Import OCR service
print("\n[TEST 1] Importing OCR service...")
try:
    from ocr_service import run_ocr
    print("[OK] ocr_service.run_ocr imported")
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

# Test 2: Tesseract
print("\n[TEST 2] Checking Tesseract OCR...")
try:
    import pytesseract
    from ocr.gold import TESSERACT_PATH
    print(f"  Path: {TESSERACT_PATH}")
    print(f"  Exists: {TESSERACT_PATH.exists()}")
    if TESSERACT_PATH.exists():
        version = pytesseract.get_tesseract_version()
        print(f"[OK] Tesseract {version}")
    else:
        print("[FAIL] Tesseract not found!")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

# Test 3: PDF support
print("\n[TEST 3] Checking PDF support...")
try:
    from pdf2image import convert_from_path
    from ocr.gold import POPPLER_PATH
    print(f"  Poppler: {POPPLER_PATH}")
    print(f"  Exists: {POPPLER_PATH.exists()}")
    print("[OK] PDF support available")
except ImportError:
    print("[WARN] pdf2image not installed")

# Test 4: Find sample files
print("\n[TEST 4] Looking for sample invoices...")
uploads_dir = Path("uploads")
if uploads_dir.exists():
    pdf_files = list(uploads_dir.glob("*.pdf"))
    if pdf_files:
        test_file = pdf_files[0]
        print(f"[OK] Found {len(pdf_files)} PDF(s)")
        print(f"  Testing: {test_file.name}")

        # Test 5: Run actual OCR
        print(f"\n[TEST 5] Running OCR on sample file...")
        try:
            result = run_ocr(str(test_file))
            print("[OK] OCR execution completed!")

            print(f"\n  OCR Status: {result.get('ocr_status')}")
            ocr_raw = result.get('ocr_raw', {})
            print(f"  Invoice No: {ocr_raw.get('facture')}")
            print(f"  Date: {ocr_raw.get('date')}")
            print(f"  Amount TTC: {ocr_raw.get('montant_ttc')}")

            mapped = result.get('mapped', {})
            print(f"\n  Mapped to DB:")
            print(f"  - invoice_no: {mapped.get('invoice_no')}")
            print(f"  - net_a_payer: {mapped.get('net_a_payer')}")
            print(f"  - kwh_consumed: {mapped.get('kwh_consumed')}")

        except Exception as e:
            print(f"[FAIL] OCR execution error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[WARN] No PDF files in uploads/")
else:
    print("[WARN] uploads/ directory not found")

# Test 6: Backend integration
print("\n[TEST 6] Checking backend integration...")
try:
    from routers.invoices import router
    endpoints = [r.path for r in router.routes if hasattr(r, 'path')]
    print(f"[OK] Invoice router loaded")
    print(f"  Endpoints: {endpoints}")
except Exception as e:
    print(f"[FAIL] {e}")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
print("\nIf OCR test passed, the backend is working correctly.")
print("\nPossible issues if OCR still not triggering from UI:")
print("1. Backend server not running (run: python back/main.py)")
print("2. Frontend pointing to wrong API URL")
print("3. CORS or authentication issues")
print("4. Check browser console (F12) for errors")
print("5. Check FastAPI logs during file upload")
