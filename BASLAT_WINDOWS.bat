@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Once KUR_WINDOWS.bat dosyasini calistirin.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m projection_pen
if errorlevel 1 pause
