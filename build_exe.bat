@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ===========================================
echo Создание EXE файла для Unified Parser
echo ===========================================

REM 1. Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Установите Python 3.8+ и добавьте его в PATH.
    pause
    exit /b 1
)
echo [OK] Python найден.

REM 2. Установка зависимостей
echo [INFO] Установка/обновление зависимостей...
pip install --upgrade pip
pip install pyinstaller PyQt5 selenium webdriver-manager playwright pandas openpyxl packaging

REM 3. Установка браузеров Playwright (КРИТИЧНО ВАЖНО)
echo [INFO] Установка браузеров Playwright (это может занять время)...
playwright install chromium
playwright install firefox
playwright install webkit

REM 4. Очистка перед сборкой
echo [INFO] Очистка временных файлов...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "UnifiedParser.spec" del /q "UnifiedParser.spec"

REM 5. Сборка EXE
echo [INFO] Запуск сборки PyInstaller...
echo Это может занять несколько минут...

pyinstaller ^
    --name "UnifiedParser" ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data "eis_parser.py;." ^
    --add-data "link_finder.py;." ^
    --hidden-import "PyQt5" ^
    --hidden-import "PyQt5.QtCore" ^
    --hidden-import "PyQt5.QtGui" ^
    --hidden-import "PyQt5.QtWidgets" ^
    --hidden-import "selenium" ^
    --hidden-import "selenium.webdriver" ^
    --hidden-import "selenium.webdriver.chrome" ^
    --hidden-import "selenium.webdriver.chrome.options" ^
    --hidden-import "selenium.webdriver.chrome.service" ^
    --hidden-import "selenium.webdriver.common.by" ^
    --hidden-import "selenium.webdriver.support.ui" ^
    --hidden-import "selenium.webdriver.support.expected_conditions" ^
    --hidden-import "webdriver_manager" ^
    --hidden-import "webdriver_manager.chrome" ^
    --hidden-import "playwright" ^
    --hidden-import "playwright.async_api" ^
    --hidden-import "playwright._impl" ^
    --hidden-import "pandas" ^
    --hidden-import "openpyxl" ^
    --hidden-import "numpy" ^
    --hidden-import "dateutil" ^
    --hidden-import "pkg_resources" ^
    unified_parser.py

if errorlevel 1 (
    echo ===========================================
    echo [ОШИБКА] Не удалось создать EXE файл.
    echo Проверьте логи выше.
    echo ===========================================
    pause
    exit /b 1
)

echo ===========================================
echo [УСПЕХ] EXE файл создан: dist\UnifiedParser.exe
echo ===========================================
echo ВНИМАНИЕ: При первом запуске программа может
echo потребовать установки драйверов, если они
echo не найдутся во временной папке.
echo ===========================================
pause
