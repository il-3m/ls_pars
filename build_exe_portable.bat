@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   Unified Parser - Сборка портативной версии
echo ==========================================
echo.
echo Эта версия создаёт ПАПКУ с приложением, а не один EXE файл.
echo Это обеспечивает лучшую совместимость с Playwright и браузерами.
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Установите Python 3.8-3.12 с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/7] Обновление pip...
python -m pip install --upgrade pip --quiet

echo.
echo [2/7] Установка зависимостей...
pip install -r requirements.txt --quiet --default-timeout=120
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости!
    pause
    exit /b 1
)

echo.
echo [3/7] Установка браузеров Playwright...
echo Это скачает Chromium (~150 МБ). Пожалуйста, подождите...
python -m playwright install chromium
if errorlevel 1 (
    echo [ПРЕДУПРЕЖДЕНИЕ] Не удалось автоматически установить браузеры Playwright.
    echo Браузеры будут установлены при первом запуске приложения.
)

echo.
echo [4/7] Поиск пути к браузерам Playwright...
for /f "delims=" %%i in ('python -c "from playwright._impl._driver import compute_driver_executable; import os; driver = compute_driver_executable(); print(os.path.dirname(os.path.dirname(driver)))" 2^>nul') do set PW_BUNDLE_DIR=%%i
if defined PW_BUNDLE_DIR (
    echo Путь к браузерам: !PW_BUNDLE_DIR!
) else (
    echo Не удалось найти путь к браузерам. Будет использована автозагрузка при запуске.
)

echo.
echo [5/7] Очистка предыдущих сборок...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo.
echo [6/7] Сборка приложения с помощью PyInstaller...
echo Режим: onedir (папка с приложением)
echo.
echo Преимущества onedir перед onefile:
echo - Быстрый запуск (не распаковывает во временную папку)
echo - Надёжная работа с Playwright и браузерами
echo - Легче обновлять отдельные компоненты
echo.

mkdir export 2>nul

REM Сборка в режиме onedir (папка)
pyinstaller --noconfirm ^
    --onedir ^
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
    --collect-all=PyQt5 ^
    --collect-all=playwright ^
    "unified_parser.py"

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось создать приложение!
    echo Проверьте логи выше.
    pause
    exit /b 1
)

echo.
echo [7/7] Копирование в папку export...
if not exist export mkdir export
if exist "dist\Unified_Parser" (
    rmdir /s /q "export\Unified_Parser" 2>nul
    xcopy /E /I /Y "dist\Unified_Parser" "export\Unified_Parser"
)

echo.
echo ==========================================
echo СБОРКА ЗАВЕРШЕНА УСПЕШНО!
echo ==========================================
echo.
echo Портативная версия создана в папке:
echo   export\Unified_Parser\
echo.
echo Для запуска на другом компьютере:
echo   1. Скопируйте ВСЮ папку "Unified_Parser" на целевой ПК
echo   2. Запустите Unified_Parser.exe внутри папки
echo   3. При первом запуске может потребоваться:
echo      - Интернет для загрузки браузеров Playwright (~150 МБ)
echo      - Google Chrome уже установлен (для Selenium части)
echo.
echo Требования на целевом компьютере:
echo   ✓ Windows 10/11
echo   ✓ Google Chrome (для поиска ссылок через Selenium)
echo   ✓ Интернет (для первого запуска + парсинга)
echo   ✗ Python НЕ требуется!
echo.
echo Размер папки: ~200-300 МБ
echo.
echo ==========================================
echo Дополнительные опции:
echo ==========================================
echo.
echo Если вы хотите создать ОДИН EXE файл (менее рекомендуется):
echo   - Измените --onedir на --onefile в этом скрипте
echo   - Но учтите: запуск будет медленнее, возможны проблемы с Playwright
echo.
echo Для создания установщика (Inno Setup):
echo   - Используйте ISCC для создания setup.exe из этой папки
echo   - См. документацию BUILD_INSTRUCTIONS.md
echo.
pause
