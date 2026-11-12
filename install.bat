@echo off
chcp 65001 >nul
title Roozhano Shop Bot - Setup
cd /d "%~dp0"
echo === نصب پیش‌نیازهای ربات ===
echo.
echo [1/2] تلاش با میرور سریع (مناسب ایران)...
python -m pip install -r requirements.txt --index-url https://mirror-pypi.runflare.com/simple --timeout 60
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [2/2] میرور جواب نداد؛ تلاش با PyPI رسمی...
    python -m pip install -r requirements.txt --timeout 120
)
echo.
python -c "import aiogram; print('OK - aiogram', aiogram.__version__)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo نصب ناموفق بود! اینترنت را چک کنید و دوباره تلاش کنید.
) else (
    echo === نصب تمام شد! حالا run.bat را اجرا کنید ===
)
pause
