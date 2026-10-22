@echo off
title Kasir Toko Desktop
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_desktop.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run_desktop.py
) else (
    python run_desktop.py
)
pause
