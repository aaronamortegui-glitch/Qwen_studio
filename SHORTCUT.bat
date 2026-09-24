@echo off
REM Creates a desktop shortcut to RUN.bat carrying the QwenStudio icon.
REM A .bat file cannot hold an icon itself; a shortcut can.
REM WindowStyle 7 is minimised: the console is not hidden, only kept out of
REM the way, because it is where progress and any error appear.
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" ^
  "  (Join-Path ([Environment]::GetFolderPath('Desktop')) 'QwenStudio.lnk'));" ^
  "$s.TargetPath=(Join-Path '%~dp0' 'RUN.bat');" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation=(Join-Path '%~dp0' 'QwenStudio.ico');" ^
  "$s.Description='QwenStudio - local Qwen-Image 2.1';" ^
  "$s.WindowStyle=7;" ^
  "$s.Save()"

if errorlevel 1 (
  echo.
  echo   Could not create the shortcut.
  pause
  exit /b 1
)

echo.
echo   QwenStudio is on your desktop.
echo.
pause
