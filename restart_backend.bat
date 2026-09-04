@echo off
echo ============================================
echo Stopping all Python backend processes...
echo ============================================
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *" 2>nul
timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo Starting InvoiceFlow Backend Server...
echo ============================================
cd /d "%~dp0back"
echo.
echo Backend will start on http://localhost:8000
echo All requests will be logged below
echo Press Ctrl+C to stop the server
echo ============================================
echo.
python -m uvicorn main:app --reload --port 8000 --log-level info
