# Unified Parser - Инструкция по сборке EXE

## Требования для сборки
- Windows 10/11
- Python 3.8 - 3.12 (обязательно!)
- Стабильное интернет-соединение
- Минимум 2 ГБ свободного места на диске

## Файлы проекта
В одной папке должны находиться:
- `unified_parser.py` - главный файл программы
- `eis_parser.py` - модуль парсинга
- `link_finder.py` - модуль поиска ссылок
- `requirements.txt` - зависимости
- `build_exe.bat` - скрипт сборки

## Автоматическая сборка (рекомендуется)

1. Запустите `build_exe.bat` двойным кликом
2. Дождитесь завершения процесса (5-15 минут в зависимости от скорости интернета)
3. Готовый EXE файл появится в папке `export\Unified_Parser.exe`

## Ручная сборка (если автоматическая не работает)

Откройте командную строку (cmd) в папке проекта и выполните:

```bat
REM 1. Обновить pip
python -m pip install --upgrade pip

REM 2. Установить зависимости
pip install -r requirements.txt

REM 3. Установить браузеры Playwright
python -m playwright install chromium

REM 4. Собрать EXE
pyinstaller --onefile --windowed --name "Unified_Parser" ^
    --add-data "<PLAYWRIGHT_PATH>;playwright/driver" ^
    --hidden-import=playwright.async_api ^
    --hidden-import=eis_parser ^
    --hidden-import=link_finder ^
    --collect-all=PyQt5 ^
    unified_parser.py
```

Где `<PLAYWRIGHT_PATH>` - путь к установленным браузерам Playwright.
Обычно это: `C:\Users\<USER>\AppData\Local\ms-playwright`

## Проверка работы

После сборки:
1. Скопируйте `export\Unified_Parser.exe` в любую папку
2. Запустите exe файл
3. Программа должна открыться без ошибок

## Требования на целевом компьютере

Для работы готового EXE файла нужно:
- ✅ Windows 10 или 11
- ✅ Google Chrome (желательно последней версии)
- ✅ Подключение к интернету
- ❌ Python НЕ требуется
- ❌ Никаких дополнительных установок НЕ нужно

## Возможные проблемы и решения

### Ошибка "Python not found"
Установите Python 3.8-3.12 с https://www.python.org/downloads/
При установке отметьте галочку "Add Python to PATH"

### Ошибка при установке зависимостей
- Проверьте интернет-соединение
- Попробуйте использовать зеркало:
  ```bat
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

### Ошибка Playwright browsers
- Убедитесь, что у вас есть 500 МБ свободного места
- Запустите от имени администратора
- Временно отключите антивирус

### EXE файл не запускается
- Проверьте, что Google Chrome установлен
- Запустите от имени администратора
- Проверьте логи в файле `unified_parser_log.txt`

### Антивирус блокирует EXE
Это ложное срабатывание. Добавьте папку с программой в исключения.

## Размер EXE файла

Готовый файл будет размером около 300-400 МБ, так как включает:
- Интерпретатор Python
- Все библиотеки (PyQt5, Playwright, Selenium и др.)
- Браузер Chromium для Playwright (~150 МБ)

## Контакты

При возникновении проблем проверьте лог-файл `unified_parser_log.txt`
