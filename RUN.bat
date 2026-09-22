@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo   The environment is missing. Run INSTALL.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m qwenstudio.app
pause
