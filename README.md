# Samba Wizard

Milestone 1 is a clickable mock wizard for setting up one private Samba share.
It uses FastAPI, Jinja2 templates, and plain CSS. The app uses mock data only
and does not install software, edit system files, mount drives, or change Samba
configuration.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

## Mock flow

The clickable flow includes:

```text
Welcome -> System Check -> Drive Selection -> Share Name -> User Setup -> Review -> Apply -> Done
```

The Review and Done pages reflect the mock choices stored in the browser
session for the current run.
