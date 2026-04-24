@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo Создание EXE файла для Unified Parser
echo ============================================
echo.

REM Проверка наличия Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH.
    echo Установите Python и добавьте его в PATH.
    pause
    exit /b 1
)

echo [1/5] Проверка версии Python...
python --version

echo.
echo [2/5] Установка необходимых зависимостей...
pip install --upgrade pip
pip install pyinstaller PyQt5 selenium webdriver-manager playwright pandas openpyxl

echo.
echo [3/5] Установка браузеров Playwright...
python -m playwright install chromium

echo.
echo [4/5] Создание спецификации PyInstaller...
echo Создаем файл unified_parser.spec...

REM Удаляем старый spec файл если есть
if exist unified_parser.spec del unified_parser.spec

REM Создаем spec файл построчно, чтобы избежать проблем с кодировкой и буферизацией
echo # -*- mode: python ; coding: utf-8 -*- > unified_parser.spec
echo. >> unified_parser.spec
echo block_cipher = None >> unified_parser.spec
echo. >> unified_parser.spec
echo a = Analysis( >> unified_parser.spec
echo     ['unified_parser.py'], >> unified_parser.spec
echo     pathex=[], >> unified_parser.spec
echo     binaries=[], >> unified_parser.spec
echo     datas=[ >> unified_parser.spec
echo         ('eis_parser.py', '.'), >> unified_parser.spec
echo         ('link_finder.py', '.'), >> unified_parser.spec
echo     ], >> unified_parser.spec
echo     hiddenimports=[ >> unified_parser.spec
echo         'PyQt5', >> unified_parser.spec
echo         'PyQt5.QtCore', >> unified_parser.spec
echo         'PyQt5.QtGui', >> unified_parser.spec
echo         'PyQt5.QtWidgets', >> unified_parser.spec
echo         'selenium', >> unified_parser.spec
echo         'selenium.webdriver', >> unified_parser.spec
echo         'selenium.webdriver.chrome', >> unified_parser.spec
echo         'selenium.webdriver.chrome.options', >> unified_parser.spec
echo         'selenium.webdriver.chrome.service', >> unified_parser.spec
echo         'selenium.webdriver.common.by', >> unified_parser.spec
echo         'selenium.webdriver.support.ui', >> unified_parser.spec
echo         'selenium.webdriver.support.expected_conditions', >> unified_parser.spec
echo         'webdriver_manager', >> unified_parser.spec
echo         'webdriver_manager.chrome', >> unified_parser.spec
echo         'playwright', >> unified_parser.spec
echo         'playwright.async_api', >> unified_parser.spec
echo         'pandas', >> unified_parser.spec
echo         'openpyxl', >> unified_parser.spec
echo         'pkg_resources.py2_warn', >> unified_parser.spec
echo         'numpy', >> unified_parser.spec
echo         'dateutil', >> unified_parser.spec
echo         'dateutil.zoneinfo', >> unified_parser.spec
echo     ], >> unified_parser.spec
echo     hookspath=[], >> unified_parser.spec
echo     hooksconfig={}, >> unified_parser.spec
echo     runtime_hooks=[], >> unified_parser.spec
echo     excludes=[], >> unified_parser.spec
echo     win_no_prefer_redirects=False, >> unified_parser.spec
echo     win_private_assemblies=False, >> unified_parser.spec
echo     cipher=block_cipher, >> unified_parser.spec
echo     noarchive=False, >> unified_parser.spec
echo ) >> unified_parser.spec
echo. >> unified_parser.spec
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher) >> unified_parser.spec
echo. >> unified_parser.spec
echo exe = EXE( >> unified_parser.spec
echo     pyz, >> unified_parser.spec
echo     a.scripts, >> unified_parser.spec
echo     a.binaries, >> unified_parser.spec
echo     a.zipfiles, >> unified_parser.spec
echo     a.datas, >> unified_parser.spec
echo     [], >> unified_parser.spec
echo     name='UnifiedParser', >> unified_parser.spec
echo     debug=False, >> unified_parser.spec
echo     bootloader_ignore_signals=False, >> unified_parser.spec
echo     strip=False, >> unified_parser.spec
echo     upx=True, >> unified_parser.spec
echo     upx_exclude=[], >> unified_parser.spec
echo     runtime_tmpdir=None, >> unified_parser.spec
echo     console=False, >> unified_parser.spec
echo     disable_windowed_traceback=False, >> unified_parser.spec
echo     argv_emulation=False, >> unified_parser.spec
echo     target_arch=None, >> unified_parser.spec
echo     codesign_identity=None, >> unified_parser.spec
echo     entitlements_file=None, >> unified_parser.spec
echo     icon=None, >> unified_parser.spec
echo ) >> unified_parser.spec

REM Проверка создания файла
if not exist unified_parser.spec (
    echo [ОШИБКА] Не удалось создать файл unified_parser.spec
    pause
    exit /b 1
)
echo Файл unified_parser.spec успешно создан.

echo.
echo [5/5] Сборка EXE файла...
echo Это может занять несколько минут...
python -m PyInstaller --clean unified_parser.spec

echo.
echo ============================================
if exist "dist\UnifiedParser.exe" (
    echo УСПЕШНО! EXE файл создан: dist\UnifiedParser.exe
    echo.
    echo ВАЖНО: Для работы программы необходимо:
    echo 1. Установленный Google Chrome на целевом компьютере
    echo 2. Скопируйте папку 'dist' на целевой компьютер
    echo 3. Запустите UnifiedParser.exe из папки dist
    echo.
    echo Примечание: При первом запуске может потребоваться
    echo установка драйвера Chrome через webdriver-manager.
) else (
    echo [ОШИБКА] Не удалось создать EXE файл.
    echo Проверьте логи выше для деталей.
)
echo ============================================
pause
