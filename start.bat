@echo off
cd /d %~dp0
echo === Unicus Diagnostics - Starting ===
echo.

if not exist .env (
    echo WARNING: No .env file found. Using default credentials ^(not secure for production^).
    echo Copy .env.example to .env and edit with your own passwords.
    echo.
)

echo Step 1: Starting Cassandra (Docker)...
docker compose -f DataBase\docker-compose.unicus.yml up -d cassandra
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found or failed. Install Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/
    pause
    exit /b 1
)

echo.
echo Step 2: Waiting for Cassandra to be ready (may take 1-2 min first time)...
set RETRIES=0
:wait_loop
set /a RETRIES+=1
if %RETRIES% gtr 36 (
    echo [ERROR] Cassandra did not become healthy within ~6 minutes. Check Docker logs.
    pause
    exit /b 1
)
timeout /t 10 /nobreak >nul
docker ps --filter name=unicus-cassandra --format "{{.Status}}" | findstr "(healthy)" >nul
if %errorlevel% neq 0 goto wait_loop
echo Cassandra is healthy!

echo.
echo Step 3: Installing dependencies...
cd DataBase
if exist ..\venv\Scripts\activate.bat call ..\venv\Scripts\activate.bat
if exist ..\.venv\Scripts\activate.bat call ..\.venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Check that Python 3.10+ and pip are installed.
    pause
    exit /b 1
)

echo.
echo Step 4: Starting Unicus Backend...
python -m unicus_lims
pause
