@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo   The environment is missing. Run INSTALL.bat first.
  pause
  exit /b 1
)
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
".venv\Scripts\python.exe" -m qwenstudio.app
pause
