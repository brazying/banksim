@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -c "import PyQt6, matplotlib" >nul 2>&1
if errorlevel 1 (
    echo Installing application dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

echo Starting bankSim...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo bankSim could not be started. Check the messages above.
pause
exit /b 1