@echo off
chcp 65001 >nul
echo ====================================
echo Создание EXE файла парсера
echo ====================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден в системе!
    echo Установите Python с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Установка зависимостей...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости!
    pause
    exit /b 1
)
echo Готово!

echo.
echo [2/4] Очистка предыдущих сборок...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo.
echo [3/4] Сборка EXE файла (это может занять несколько минут)...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Парсер_Лекарств" ^
    --icon=NONE ^
    --add-data "requirements.txt;." ^
    --hidden-import=pkg_resources.py2_warn ^
    --hidden-import=selenium ^
    --hidden-import=webdriver_manager ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    "ЛС-парсер-лайт.py"

if errorlevel 1 (
    echo.
    echo ОШИБКА: Не удалось создать EXE файл!
    echo Проверьте логи выше.
    pause
    exit /b 1
)

echo.
echo [4/4] Копирование EXE в папку export...
if not exist export mkdir export
copy /Y dist\Парсер_Лекарств.exe export\ >nul

echo.
echo ====================================
echo СБОРКА ЗАВЕРШЕНА УСПЕШНО!
echo ====================================
echo.
echo EXE файл создан в папке: export\Парсер_Лекарств.exe
echo.
echo ВАЖНО: Для работы парсера на целевом компьютере потребуется:
echo 1. Установленный Google Chrome браузер
echo 2. Доступ к интернету
echo.
echo Файл можно перенести на любой компьютер с Windows 10/11
echo и запускать без установленного Python.
echo.
pause
