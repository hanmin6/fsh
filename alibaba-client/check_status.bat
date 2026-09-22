@echo off
setlocal
cd /d "%~dp0"
python check_status.py
echo.
pause
