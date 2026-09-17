@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: Chuyen den dung thu muc chua file run.bat
cd /d "%~dp0"

echo ================================================================
echo   Khoi dong EduExam AI 2026 - Tao va Tron De Kiem Tra 2026 - 2027
echo ================================================================
echo.

:: 1. Tim kiem trinh thuc thi Python
set "PY_CMD="

if exist "C:\ProgramData\miniconda3\python.exe" (
    set "PY_CMD=C:\ProgramData\miniconda3\python.exe"
) else if exist "%USERPROFILE%\miniconda3\python.exe" (
    set "PY_CMD=%USERPROFILE%\miniconda3\python.exe"
) else if exist "%USERPROFILE%\anaconda3\python.exe" (
    set "PY_CMD=%USERPROFILE%\anaconda3\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo [LOI] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python hoac them Python vao bien moi truong PATH.
    echo.
    pause
    exit /b 1
)

set "PORT=8888"
echo Tim thay trinh thuc thi: %PY_CMD%
echo Dang khoi dong may chu tai: http://localhost:8888
echo Nhan Ctrl+C de dung may chu.
echo.

:: 2. Tu dong mo trinh duyet sau 1 giay
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8888"

:: 3. Chay ung dung
"%PY_CMD%" main.py
if errorlevel 1 (
    echo.
    echo [THONG BAO] May chu da dung.
    pause
)
