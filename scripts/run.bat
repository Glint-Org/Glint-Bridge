@echo off
cd /d "%~dp0.."

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
)

venv\Scripts\python.exe bridge\main.py %*
