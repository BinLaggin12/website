@echo off
cd /d "C:\Users\write\OneDrive\Documents\Website-Project"
start /B python server.py
timeout /t 2 >nul
start http://localhost:3000
echo Server started at http://localhost:3000
pause