# InvoiceFlow Full Setup Guide

This guide is intended to be used on a fresh Windows PC so the project can be installed and run without missing tools or configuration.

It includes:
- required software
- Python environment setup
- exact project dependencies
- bundled OCR tool paths already included in the repo
- SQL Server setup
- environment variables
- start commands
- troubleshooting

---

## 1. Required software to install

### 1.1 Python 3.11
Install Python 3.11.x and make sure the checkbox below is enabled during setup:
- Add Python to PATH

Verify with:

```powershell
python --version
```

If Python is installed but not detected, reopen the terminal or restart the PC.

### 1.2 Git (recommended)
Install Git for Windows for cloning the project and easier version control.

### 1.3 Visual Studio Code (recommended)
Install VS Code and add these extensions:
- Python
- Pylance
- Jupyter (optional)

### 1.4 SQL Server
This project uses SQL Server with SQLAlchemy and pyodbc.

You can use either:
- SQL Server Developer / Express / Standard
- SQL Server LocalDB

The app expects a working SQL Server instance with permissions for the current Windows user.

### 1.5 ODBC Driver 18 for SQL Server
Install this Microsoft driver:
- ODBC Driver 18 for SQL Server

This is mandatory because the app config uses `pyodbc` and `mssql+pyodbc`.

### 1.6 Tesseract OCR
Install Tesseract OCR from the official Windows build.

Typical installation folder:
- `C:\Program Files\Tesseract-OCR\tesseract.exe`

Also ensure the Tesseract install folder is added to PATH.

### 1.7 Poppler for PDF rendering
Install Poppler for Windows.

Typical folder:
- `C:\poppler\bin`

The project also contains a bundled Poppler copy in the repo, so it can work without a global installation in many cases.

---

## 2. Project dependencies

The backend dependencies are stored in:
- [back/requirements.txt](../back/requirements.txt)

Install them in a virtual environment using:

```powershell
cd "C:\path\to\Projet PFA_FR"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r back\requirements.txt
```

Installed backend packages:

```txt
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
pyodbc>=5.1
pydantic>=2.7
email-validator>=2.1
python-jose[cryptography]>=3.3
bcrypt>=4.1
python-multipart>=0.0.9
pytesseract>=0.3.10
opencv-python-headless>=4.8
numpy>=1.24
pdf2image>=1.16
```

### Main frameworks used
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic
- PyJWT / python-jose
- bcrypt
- pyodbc
- Python multipart
- pytesseract
- OpenCV
- NumPy
- pdf2image

---

## 3. OCR tools included in the project

This project already includes the OCR software in the repo, so you do not have to manually download them for this project to work in the local setup.

Project OCR folder:
- [back/ocr](../back/ocr)

Important paths used by the code:
- Tesseract: [back/ocr/Tesseract-OCR/tesseract.exe](../back/ocr/Tesseract-OCR/tesseract.exe)
- Tesseract data folder: [back/ocr/Tesseract-OCR/tessdata](../back/ocr/Tesseract-OCR/tessdata)
- Poppler: [back/ocr/poppler-26.02.0/Library/bin](../back/ocr/poppler-26.02.0/Library/bin)

The project sets these automatically in [back/ocr/gold.py](../back/ocr/gold.py#L7-L18):

```python
BASE_DIR = Path(__file__).parent
TESSERACT_PATH = BASE_DIR / "Tesseract-OCR" / "tesseract.exe"
if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)

TESSDATA_PATH = BASE_DIR / "Tesseract-OCR" / "tessdata"
if TESSDATA_PATH.exists():
    os.environ['TESSDATA_PREFIX'] = str(TESSDATA_PATH)

POPPLER_PATH = BASE_DIR / "poppler-26.02.0" / "Library" / "bin"
```

This means the app tries to use the bundled OCR folder first.

---

## 4. SQL Server configuration

The backend configuration is in:
- [back/config.py](../back/config.py)

Defaults used by this project:
- database name: `StegDB`
- server: `SE7LLI`
- driver: `ODBC Driver 18 for SQL Server`
- host: `127.0.0.1`
- port: `8000`

You can override them before running the app:

```powershell
$env:INVOICEFLOW_DB_SERVER = "SE7LLI"
$env:INVOICEFLOW_DB_NAME = "StegDB"
$env:INVOICEFLOW_DB_DRIVER = "ODBC Driver 18 for SQL Server"
$env:INVOICEFLOW_HOST = "127.0.0.1"
$env:INVOICEFLOW_PORT = "8000"
```

### SQL Server authentication
The project uses Windows trusted authentication by default:

```python
Trusted_Connection=yes;
TrustServerCertificate=yes;
```

That means the user running the project must have rights to the SQL Server instance.

---

## 5. Project folder structure

Expected project layout:

```text
Projet PFA_FR/
├── back/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── requirements.txt
│   ├── ocr/
│   │   ├── Tesseract-OCR/
│   │   ├── poppler-26.02.0/
│   │   └── gold.py
│   └── ...
├── front/
├── guide/
├── uploads/
├── index.html
├── BACKEND_GUIDE.md
├── README.md (if present)
├── .venv/
└── ...
```

---

## 6. Fresh PC installation steps

### Step 1: Install base tools
Install:
- Python 3.11
- VS Code
- Git
- SQL Server
- ODBC Driver 18
- Tesseract OCR
- Poppler

### Step 2: Clone or copy the project
Place the project in a folder such as:

```text
C:\Users\yourname\Desktop\Projet PFA_FR
```

### Step 3: Create the virtual environment

```powershell
cd "C:\Users\yourname\Desktop\Projet PFA_FR"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 4: Install Python dependencies

```powershell
pip install --upgrade pip
pip install -r back\requirements.txt
```

### Step 5: Verify SQL Server is available
Open SQL Server Management Studio or use a connection tool to ensure the database server is reachable.

If needed, update the env variables:

```powershell
$env:INVOICEFLOW_DB_SERVER = "SE7LLI"
$env:INVOICEFLOW_DB_NAME = "StegDB"
```

### Step 6: Verify OCR tools
Run:

```powershell
tesseract --version
pdftoppm -h
```

If these commands fail, add the relevant install folders to PATH and reopen the terminal.

### Step 7: Run the backend

```powershell
cd "C:\Users\yourname\Desktop\Projet PFA_FR\back"
python run.py
```

Or:

```powershell
cd "C:\Users\yourname\Desktop\Projet PFA_FR\back"
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 8: Open the app
In the browser, go to:

```text
http://127.0.0.1:8000/
```

---

## 7. Useful PowerShell commands

Create virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install requirements:

```powershell
pip install -r back\requirements.txt
```

Run backend:

```powershell
cd back
python run.py
```

Check Python version:

```powershell
python --version
```

Check Tesseract:

```powershell
tesseract --version
```

Check Poppler:

```powershell
pdftoppm -h
```

---

## 8. Common installation problems and fixes

### Problem: `pyodbc` installation fails
Fix:
- install Visual C++ Build Tools
- install ODBC Driver 18
- use Python 3.11
- reinstall the package

### Problem: SQL Server connection fails
Fix:
- confirm SQL Server service is running
- check the server name
- confirm trusted Windows authentication is enabled
- verify the Windows user has DB access

### Problem: Tesseract not found
Fix:
- install Tesseract
- add the install path to PATH
- reopen the terminal

### Problem: Poppler binaries not found
Fix:
- install Poppler or use the bundled project copy
- ensure the `bin` folder is added to PATH

### Problem: app cannot open OCR files
Fix:
- confirm the OCR files are present in the repo
- verify the app is using the local folder paths
- check that the image/PDF is valid

### Problem: backend runs but the UI is blank
Fix:
- ensure the backend is serving static files correctly
- open the page at `http://127.0.0.1:8000/`
- check the terminal output for errors

---

## 9. Final checklist before you start

Before launching the project on a new PC, confirm the following:

- [ ] Python 3.11 is installed
- [ ] Virtual environment is created
- [ ] dependencies are installed from `back/requirements.txt`
- [ ] SQL Server is running
- [ ] ODBC Driver 18 is installed
- [ ] Tesseract is installed or the project-local copy exists
- [ ] Poppler is available or the bundled version exists
- [ ] backend runs without import errors
- [ ] browser opens `http://127.0.0.1:8000/`

---

## 10. Summary

This project is designed to run on Windows and depends on:
- Python + dependencies from `back/requirements.txt`
- SQL Server with ODBC driver
- bundled OCR tools inside the repo
- Poppler for PDF conversion
- a working HTTP server and browser environment

If the environment variables and software are correct, the project can be recreated on another PC reliably.

---

## 11. Short version

If you need the fastest version of the setup, use this:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r back\requirements.txt
cd back
python run.py
```

Then open:

```text
http://127.0.0.1:8000/
```

This guide is meant to be reused on another machine without needing additional context.
