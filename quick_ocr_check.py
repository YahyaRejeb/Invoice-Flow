# Quick OCR Status Check
import sys
sys.path.insert(0, 'back')

print("Checking OCR connection...")

# 1. Can we import?
try:
    from ocr_service import run_ocr
    print("[OK] OCR module imported")
except Exception as e:
    print(f"[ERROR] Cannot import: {e}")
    sys.exit(1)

# 2. Is Tesseract available?
try:
    from ocr.gold import TESSERACT_PATH
    import pytesseract

    if TESSERACT_PATH.exists():
        print(f"[OK] Tesseract found at: {TESSERACT_PATH}")
        try:
            version = pytesseract.get_tesseract_version()
            print(f"[OK] Tesseract version: {version}")
        except:
            print("[WARN] Cannot get Tesseract version")
    else:
        print("[ERROR] Tesseract NOT found!")
except Exception as e:
    print(f"[ERROR] Tesseract check failed: {e}")

# 3. Check backend router
try:
    from routers.invoices import upload_invoice
    print("[OK] Upload endpoint exists")
except Exception as e:
    print(f"[ERROR] Upload endpoint: {e}")

print("\n=== CONCLUSION ===")
print("If all checks passed, OCR is properly connected.")
print("\nTo debug further, check:")
print("1. Is backend running? (python back/main.py)")
print("2. Browser console errors? (Press F12)")
print("3. Network tab shows /invoices/upload request?")
print("4. Check backend terminal for errors during upload")
