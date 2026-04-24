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

(
echo # -*- mode: python ; coding: utf-8 -*-
echo.
echo block_cipher = None
echo.
echo a = Analysis(
echo     ['unified_parser.py'],
echo     pathex=[],
echo     binaries=[],
echo     datas=[
echo         ('eis_parser.py', '.'),
echo         ('link_finder.py', '.'),
echo     ],
echo     hiddenimports=[
echo         'PyQt5',
echo         'PyQt5.QtCore',
echo         'PyQt5.QtGui',
echo         'PyQt5.QtWidgets',
echo         'selenium',
echo         'selenium.webdriver',
echo         'selenium.webdriver.chrome',
echo         'selenium.webdriver.chrome.options',
echo         'selenium.webdriver.chrome.service',
echo         'selenium.webdriver.common.by',
echo         'selenium.webdriver.support.ui',
echo         'selenium.webdriver.support.expected_conditions',
echo         'webdriver_manager',
echo         'webdriver_manager.chrome',
echo         'playwright',
echo         'playwright.async_api',
echo         'pandas',
echo         'openpyxl',
echo         'pkg_resources.py2_warn',
echo         'numpy',
echo         'dateutil',
echo         'dateutil.zoneinfo',
echo     ],
echo     hookspath=[],
echo     hooksconfig={},
echo     runtime_hooks=[],
echo     excludes=[],
echo     win_no_prefer_redirects=False,
echo     win_private_assemblies=False,
echo     cipher=block_cipher,
echo     noarchive=False,
echo )
echo.
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
echo.
echo exe = EXE(
echo     pyz,
echo     a.scripts,
echo     a.binaries,
echo     a.zipfiles,
echo     a.datas,
echo     [],
echo     name='UnifiedParser',
echo     debug=False,
echo     bootloader_ignore_signals=False,
echo     strip=False,
echo     upx=True,
echo     upx_exclude=[],
echo     runtime_tmpdir=None,
echo     console=False,
echo     disable_windowed_traceback=False,
echo     argv_emulation=False,
echo     target_arch=None,
echo     codesign_identity=None,
echo     entitlements_file=None,
echo     icon=None,
echo )
) > unified_parser.spec

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
