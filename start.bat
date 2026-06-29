@echo off
cd /d %~dp0
echo Starting Cassandra...
docker compose -f DataBase\docker-compose.unicus.yml up -d cassandra
echo Waiting 30s for Cassandra to be ready...
timeout /t 30 /nobreak >nul
echo Starting Unicus Backend...
cd DataBase
python -m unicus_lims
pause
