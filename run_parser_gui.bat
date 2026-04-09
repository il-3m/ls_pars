@echo off
chcp 65001 >nul
title Парсер лекарств ЕИС

cd /d "%~dp0"

echo ====================================================
echo    ⚕️  ПАРСЕР ЛЕКАРСТВЕННЫХ СРЕДСТВ ЕИС
echo ====================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Ошибка: Python не найден в системе!
    echo Установите Python 3.9+ и добавьте его в PATH
    pause
    exit /b 1
)

echo Проверка зависимостей...
python -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  PyQt5 не установлен. Установка...
    pip install PyQt5 --quiet
)

python -c "import selenium" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Selenium не установлен. Установка...
    pip install selenium webdriver-manager --quiet
)

python -c "import pandas" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Pandas не установлен. Установка...
    pip install pandas openpyxl --quiet
)

echo.
echo ✅ Запуск интерфейса парсера...
echo.
echo ────────────────────────────────────────────────────
echo Если окно не открылось, проверьте установку Python
echo ────────────────────────────────────────────────────
echo.

python parser_launcher.py

pause