@echo off
REM stroke-order local server (double-click to run)
REM ASCII-only: cmd.exe parses .bat in the OEM codepage, so any
REM UTF-8 Chinese inside would garble and break line parsing.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" http://127.0.0.1:8000/
python -m uvicorn stroke_order.web.server:app --host 127.0.0.1 --port 8000
pause
