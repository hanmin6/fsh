@echo off
setlocal
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

echo ======================================================
echo   Alibaba CRM launcher
echo ======================================================

where docker >nul 2>&1
if errorlevel 1 (
	echo ERROR: docker.exe was not found in PATH.
	pause
	exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
	echo ERROR: python.exe was not found in PATH.
	pause
	exit /b 1
)

echo [1/3] Starting CRM containers...
docker start fusanhe-alibaba-manual-db-1 fusanhe-alibaba-manual-espocrm-1
if errorlevel 1 echo WARNING: one or more CRM containers could not be started.

echo [2/3] Starting inbound sync daemon...
start "Alibaba Inbound Sync Daemon" /D "%APP_DIR%" cmd /k python alibaba_messenger\run_sync.py daemon

echo [3/3] Starting outbound worker...
start "Alibaba Outbound Worker" /D "%APP_DIR%" cmd /k python alibaba_messenger\run_worker.py

echo ======================================================
echo   Launcher finished. Keep the two worker windows open.
echo   CRM: http://localhost:18080
echo ======================================================
pause
