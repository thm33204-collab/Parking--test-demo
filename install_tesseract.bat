@echo off
title Cai dat Tesseract OCR tu dong
chcp 65001 >nul

:: Check for administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :admin
) else (
    goto :request_admin
)

:request_admin
echo ============================================================
echo YEU CAU QUYEN ADMIN DE CAI DAT TESSERACT OCR
echo ============================================================
echo.
echo Dang yeu cau quyen Administrator de chay trinh cai dat...
powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
exit /b

:admin
echo ============================================================
echo TAI VA CAI DAT TESSERACT OCR TU DONG
echo ============================================================
echo.
echo 1. Dang tai bo cai dat Tesseract OCR tu repository UB-Mannheim...
echo Vui long cho trong giay lat...
echo.

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe', '%TEMP%\tesseract-setup.exe')"

if %errorlevel% neq 0 (
    echo.
    echo LOI: Khong the tai xuong bo cai dat. Vui long kiem tra lai mang.
    pause
    exit /b %errorlevel%
)

echo.
echo 2. Tai xong! Bat dau cai dat tu dong (Silent Install)...
echo Tesseract se duoc cai vao: C:\Program Files\Tesseract-OCR
echo.

"%TEMP%\tesseract-setup.exe" /S

if %errorlevel% neq 0 (
    echo.
    echo LOI: Co loi trong qua trinh cai dat.
    pause
    exit /b %errorlevel%
)

echo ============================================================
echo DA CAI DAT THANH CONG TESSERACT OCR!
echo Thu muc mac dinh: C:\Program Files\Tesseract-OCR
echo ============================================================
echo.
echo Du an bay gio da co the nhan dien bien so xe that tu anh!
echo.
pause
