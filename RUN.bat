@echo off
REM Start minimised. The console is where the download progress, the profile
REM line and "that was too large for this card" appear, so it is not hidden --
REM it is put out of the way. This is how a .bat minimises itself: start a
REM second copy minimised, and let the first one go.
if not "%~1"=="min" (
  start "QwenStudio" /min cmd /c ""%~f0" min"
  exit /b
)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo   The environment is missing. Run INSTALL.bat first.
  pause
  exit /b 1
)
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
".venv\Scripts\python.exe" -m qwenstudio.app
pause
