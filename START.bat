@echo off
title LYDRIVE: ZERO GRAVITY - INITIALIZING...
color 0A
cls

echo ======================================================
echo           LYDRIVE: ZERO GRAVITY SYSTEM v2.0
echo                DEVELOPED BY LYTIX
echo ======================================================
echo.

:: 1. 檢查 Python 環境
echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit
)
echo [OK] Python detected.

:: 2. 自動更新/安裝必要套件
echo [2/4] Verifying Core Modules (Flask, Cryptography, etc.)...
python -m pip install --upgrade pip >nul
python -m pip install flask flask-sqlalchemy flask-login flask-bcrypt authlib requests cryptography >nul
echo [OK] Modules verified.

:: 3. 檢查資料夾結構
echo [3/4] Validating Storage Structure...
if not exist "static\storage" mkdir "static\storage"
if not exist "static\vault" mkdir "static\vault"
if not exist "templates" mkdir "templates"
echo [OK] Directories synchronized.

:: 4. 啟動伺服器
echo [4/4] Launching Nexus Core at http://127.0.0.1:5000
echo.
echo >> SYSTEM LOGS:
echo ------------------------------------------------------
python app.py
pause