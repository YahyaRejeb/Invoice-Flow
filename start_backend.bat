@echo off
REM Start InvoiceFlow Backend with Logging
cd /d "%~dp0back"
echo Starting InvoiceFlow Backend Server...
echo Logging enabled - you will see all requests here
echo ================================================
python -m uvicorn main:app --reload --port 8000 --log-level info
pause
