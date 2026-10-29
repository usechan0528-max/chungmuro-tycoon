@echo off
setlocal

cd /d "%~dp0"
title ChungmuroTycoon

echo ========================================
echo ChungmuroTycoon - development runner
echo ========================================
echo.

set "PYTHON_EXE=.venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" goto ensure_db

echo Creating local Python virtual environment...
py -3.12 -m venv .venv 2>nul
if errorlevel 1 py -3.11 -m venv .venv 2>nul
if errorlevel 1 python -m venv .venv 2>nul

if not exist "%PYTHON_EXE%" (
    echo.
    echo Failed to create .venv.
    echo Install Python 3.11 or 3.12, then run this file again.
    echo.
    pause
    exit /b 1
)

echo Installing required packages...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto pip_failed
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto pip_failed

:ensure_db
if exist "data\game.db" goto run_game

echo Initializing game database...
"%PYTHON_EXE%" scripts\init_db.py
if errorlevel 1 goto db_failed
"%PYTHON_EXE%" scripts\seed_db.py
if errorlevel 1 goto db_failed

:run_game
echo Starting ChungmuroTycoon...
"%PYTHON_EXE%" main.py
if errorlevel 1 goto run_failed
exit /b 0

:pip_failed
echo.
echo Package installation failed.
echo Check your internet connection and Python installation.
echo.
pause
exit /b 1

:db_failed
echo.
echo Database initialization failed.
echo.
pause
exit /b 1

:run_failed
echo.
echo The game closed with an error.
echo.
pause
exit /b 1
