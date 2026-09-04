# Quick Backend Health Check
import sys
import requests
import time

print("=" * 60)
print("InvoiceFlow Backend Health Check")
print("=" * 60)

# Check if backend is responding
try:
    response = requests.get("http://localhost:8000/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"\n[OK] Backend is running!")
        print(f"     Service: {data.get('service')}")
        print(f"     Version: {data.get('version')}")
    else:
        print(f"\n[ERROR] Backend returned status {response.status_code}")
except requests.exceptions.ConnectionError:
    print("\n[ERROR] Cannot connect to backend on port 8000")
    print("        Please run: restart_backend.bat")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] {e}")
    sys.exit(1)

# Check if we can access API endpoints
print("\n" + "=" * 60)
print("Testing API Endpoints")
print("=" * 60)

endpoints = [
    ("GET", "/health", "Health check"),
    ("GET", "/docs", "API documentation"),
]

for method, path, description in endpoints:
    try:
        url = f"http://localhost:8000{path}"
        response = requests.request(method, url, timeout=3)
        status = "[OK]" if response.status_code < 400 else "[FAIL]"
        print(f"{status} {method:4s} {path:20s} - {description}")
    except Exception as e:
        print(f"[FAIL] {method:4s} {path:20s} - {e}")

print("\n" + "=" * 60)
print("Check Complete!")
print("=" * 60)
print("\nIf backend is OK, check browser console (F12) for frontend errors.")
print("Try uploading a file and watch this terminal for OCR logs.")
