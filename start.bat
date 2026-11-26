@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if not errorlevel 1 py -3.11 -m venv .venv
if exist ".venv\Scripts\python.exe" goto dependencies
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto use_launcher
python -m venv .venv
if errorlevel 1 goto failed
goto dependencies
:use_launcher
py -3 -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -c "import rawpy; from PIL import Image, ImageCms" >nul 2>nul
if not errorlevel 1 goto run
echo Installing dependencies. Internet access is required on first run...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:run
".venv\Scripts\python.exe" cr2_converter.py %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Failed. Please check the message above. Python 3.10+ is required.
pause
exit /b 1
