@echo off
chcp 65001 >nul
echo =====================================================
echo Сборка LS_Parser_Light.exe
echo =====================================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    echo Установите Python с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Установка зависимостей...
pip install pyinstaller pandas PyQt5 selenium webdriver-manager requests openpyxl --quiet

echo [2/4] Очистка предыдущих сборок...
rmdir /s /q build dist 2>nul
del LS_Parser_Light.spec 2>nul

echo [3/4] Компиляция в EXE...
pyinstaller --onefile --windowed --name "LS_Parser_Light" ^
    --hidden-import=pandas ^
    --hidden-import=PyQt5 ^
    --hidden-import=selenium ^
    --hidden-import=webdriver_manager ^
    --hidden-import=requests ^
    --hidden-import=openpyxl ^
    "ЛС-парсер-лайт.py"

if errorlevel 1 (
    echo.
    echo ОШИБКА при сборке! Проверьте логи выше.
    pause
    exit /b 1
)

echo.
echo [4/4] Готово!
echo =====================================================
echo EXE-файл создан: dist\LS_Parser_Light.exe
echo =====================================================
echo.
echo Теперь вы можете скопировать файл dist\LS_Parser_Light.exe
echo на любой компьютер с Windows 10/11 и запустить его.
echo Никаких дополнительных программ устанавливать не нужно!
echo.
pause
