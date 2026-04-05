@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found in PATH.
  pause
  exit /b 1
)

python eis_parser.py --gui
if errorlevel 1 (
  echo.
  echo Parser exited with error.
  pause
)