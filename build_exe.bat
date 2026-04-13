@echo off
chcp 65001 >nul
echo ====================================
echo Unified Parser EXE Builder
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in system!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo Done!

echo.
echo [2/4] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo.
echo [3/4] Installing Playwright browsers...
echo This will download Chromium browser (~150MB). Please wait...
python -m playwright install chromium
if errorlevel 1 (
    echo WARNING: Failed to install Playwright browsers automatically.
    echo The EXE will install them on first run.
)

echo.
echo [4/4] Building EXE file (this may take several minutes)...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Unified_Parser" ^
    --icon=NONE ^
    --add-data "requirements.txt;." ^
    --hidden-import=pkg_resources.py2_warn ^
    --hidden-import=selenium ^
    --hidden-import=webdriver_manager ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=playwright ^
    --hidden-import=eis_parser ^
    --hidden-import=link_finder ^
    "unified_parser.py"

if errorlevel 1 (
    echo.
    echo ERROR: Failed to create EXE file!
    echo Check logs above.
    pause
    exit /b 1
)

echo.
echo [5/5] Copying EXE to export folder...
if not exist export mkdir export
copy /Y dist\Unified_Parser.exe export\ >nul

echo.
echo ====================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ====================================
echo.
echo EXE file created in: export\Unified_Parser.exe
echo.
echo IMPORTANT: For the parser to work on the target computer you need:
echo 1. Google Chrome browser installed (for Selenium part)
echo 2. Internet access
echo 3. At FIRST RUN, Playwright will auto-install Chromium browser
echo    This takes 1-2 minutes and requires internet connection.
echo    Subsequent runs will be faster.
echo.
echo You can transfer this file to any Windows 10/11 computer
echo and run it without Python installed.
echo.
pause
