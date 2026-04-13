@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo   Unified Parser EXE Builder with Playwright Browsers
echo ==========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8-3.12 from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/6] Upgrading pip...
python -m pip install --upgrade pip --default-timeout=60 --retries=5

echo.
echo [2/6] Installing Python dependencies...
pip install -r requirements.txt --default-timeout=60 --retries=5
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [3/6] Installing Playwright browsers (this will take a while)...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright browsers.
    pause
    exit /b 1
)

echo.
echo [4/6] Finding Playwright browser installation path...
for /f "delims=" %%i in ('python -c "from playwright._impl._driver import compute_driver_executable; import os; driver = compute_driver_executable(); print(os.path.dirname(os.path.dirname(driver)))"') do set PW_BUNDLE_DIR=%%i
echo Playwright bundle directory: %PW_BUNDLE_DIR%

echo.
echo [5/6] Building EXE with PyInstaller...
mkdir export 2>nul
pyinstaller --onefile ^
    --windowed ^
    --name "Unified_Parser" ^
    --add-data "%PW_BUNDLE_DIR%;playwright/driver" ^
    --hidden-import=playwright.async_api ^
    --hidden-import=eis_parser ^
    --hidden-import=link_finder ^
    --collect-all=PyQt5 ^
    unified_parser.py
if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    pause
    exit /b 1
)

echo.
echo [6/6] Copying EXE to export folder...
if exist "dist\Unified_Parser.exe" (
    copy /Y "dist\Unified_Parser.exe" "export\"
    echo.
    echo ==========================================
    echo SUCCESS! EXE created: export\Unified_Parser.exe
    echo ==========================================
    echo.
    echo The EXE file includes:
    echo - All Python dependencies
    echo - Playwright Chromium browser (~150MB)
    echo.
    echo Requirements on target PC:
    echo - Windows 10/11
    echo - Google Chrome installed (for additional compatibility)
    echo - Internet connection
    echo - NO Python required!
    echo.
) else (
    echo [ERROR] EXE file was not created.
    pause
    exit /b 1
)

pause
