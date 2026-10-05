@echo off
title Khoi chay he thong Smart Parking
chcp 65001 >nul

echo ============================================================
echo DANG KHOI CHAY SMART PARKING WEB APP...
echo ============================================================
echo.

:: Path check
if not exist venv (
    echo [CANH BAO] Khong tim thay thu muc venv!
    echo Vui long chay lenh cai dat moi truong truoc khi khoi chay.
    pause
    exit /b
)

:: Environment config
set PYTHONUTF8=1

:: Open browser automatically
echo Dang mo trinh duyet den http://localhost:5000...
start http://localhost:5000

:: Run the Flask server
echo Dang bat server Flask...
venv\Scripts\python.exe app.py

pause
