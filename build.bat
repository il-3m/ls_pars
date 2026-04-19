@echo off
chcp 65001 >nul
echo ============================================
echo Сборка UnifiedParser.exe для Windows
echo ============================================
echo.

REM Проверяем, установлен ли Python
where python >nul 2>nul
if errorlevel 1 (
    echo ОШИБКА: Python не найден в PATH!
    echo.
    echo Пожалуйста, установите Python 3.11 с https://www.python.org/downloads/
    echo При установке отметьте галочку "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/4] Проверка версии Python...
python --version
echo.

echo [2/4] Установка зависимостей (это может занять несколько минут)...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости!
    pause
    exit /b 1
)
echo.

echo [3/4] Установка браузеров Playwright...
playwright install chromium
echo.

echo [4/4] Сборка executable файла...
pyinstaller --clean build_exe.spec
if errorlevel 1 (
    echo ОШИБКА: Не удалось собрать executable!
    pause
    exit /b 1
)
echo.

echo ============================================
echo СБОРКА ЗАВЕРШЕНА УСПЕШНО!
echo ============================================
echo.
echo Готовый файл: dist\UnifiedParser.exe
echo.
echo Вы можете скопировать UnifiedParser.exe на любой компьютер с Windows 10/11
echo и запускать его без установки Python или других программ.
echo.
echo ВАЖНО: Для работы программы нужен Google Chrome или Chromium!
echo.
pause
