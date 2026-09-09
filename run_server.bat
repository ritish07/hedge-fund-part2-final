@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py >> server.log 2>&1
