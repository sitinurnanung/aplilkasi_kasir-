@echo off
title Kasir Toko POS Server
cd /d "%~dp0"

echo ===================================================
echo   Memulai Kasir Toko...
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    echo Menggunakan virtual environment .venv...
    ".venv\Scripts\python.exe" app.py
) else if exist "venv\Scripts\python.exe" (
    echo Menggunakan virtual environment venv...
    "venv\Scripts\python.exe" app.py
) else (
    echo Menggunakan Python sistem...
    python app.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ===================================================
    echo Terjadi error. Pastikan Flask terpasang:
    echo Jalankan: pip install flask
    echo ===================================================
    pause
)
