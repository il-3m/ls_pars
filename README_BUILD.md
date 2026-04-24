# Инструкция по сборке Unified Parser в EXE для Windows

## Требования
- Windows 10/11 (64-bit)
- Python 3.8 или выше
- Минимум 2 ГБ свободного места на диске
- Visual C++ Redistributable (обычно уже установлен в Windows)

## Шаг 1: Подготовка окружения

1. Установите Python с официального сайта: https://www.python.org/downloads/
   - При установке отметьте галочку "Add Python to PATH"

2. Откройте командную строку (cmd) или PowerShell от имени администратора

3. Перейдите в папку проекта:
   ```cmd
   cd путь\к\папке\проекта
   ```

## Шаг 2: Установка зависимостей

Выполните команду для установки всех необходимых библиотек:

```cmd
pip install pyinstaller playwright selenium PyQt5 openpyxl pandas webdriver-manager
```

## Шаг 3: Установка браузеров Playwright

```cmd
playwright install chromium
```

## Шаг 4: Запуск скрипта сборки

```cmd
python build_script.py
```

Скрипт автоматически:
- Проверит и установит зависимости
- Скачает Chromium в папку проекта
- Упакует всё в один EXE файл
- Очистит временные файлы

## Шаг 5: Проверка результата

После успешной сборки:
1. Зайдите в папку `dist`
2. Там должен быть файл `UnifiedParser.exe`
3. Размер файла будет около 200-250 МБ (так как браузер встроен)

## Шаг 6: Тестирование

1. Скопируйте `UnifiedParser.exe` на чистый компьютер (без Python)
2. Запустите файл
3. Программа должна запуститься и показать GUI интерфейс

## Возможные проблемы и решения

### Ошибка "Executable doesn't exist"
**Причина:** Путь к браузеру внутри EXE не совпадает с ожидаемым.

**Решение:** Убедитесь, что `build_script.py` успешно скачал браузер до запуска PyInstaller.

### Ошибка "No module named '...'"
**Причина:** PyInstaller пропустил импорт.

**Решение:** Добавьте модуль в список `HIDDEN_IMPORTS` внутри `build_script.py`.

### Ошибка Visual C++
**Причина:** На целевом ПК нет библиотек MSVC.

**Решение:** Установите VC_redist.x64.exe с сайта Microsoft.

### EXE файл слишком большой
Это нормально! Встроенный браузер Chromium занимает ~150-200 МБ. Это гарантирует работу на любом компьютере без установки Chrome.

## Структура файлов проекта

```
project/
├── unified_parser.py      # Основной код парсера
├── eis_parser.py          # Модуль парсинга
├── link_finder.py         # Модуль поиска ссылок
├── build_script.py        # Скрипт сборки (этот файл)
├── dist/                  # Результаты сборки
│   └── UnifiedParser.exe  # Готовый EXE файл
└── README_BUILD.md        # Эта инструкция
```

## Примечания

1. **Первая сборка может занять 10-15 минут** (скачивание браузера + компиляция)
2. **Не удаляйте папку _temp_browser_cache** до завершения сборки
3. **Для повторной сборки** удалите папки `build/`, `dist/` и файл `UnifiedParser.spec`

## Альтернативный способ сборки (вручную)

Если скрипт не работает, можно собрать вручную:

```cmd
# 1. Скачать браузер в папку проекта
set PLAYWRIGHT_BROWSERS_PATH=%CD%\_browser_cache
playwright install chromium

# 2. Найти папку с браузером (например, chromium-1234)
# 3. Запустить PyInstaller
pyinstaller --name UnifiedParser ^
    --onefile ^
    --add-data "_browser_cache\chromium-*;_playwright_browser" ^
    --hidden-import="playwright.async_api" ^
    --hidden-import="selenium" ^
    --hidden-import="PyQt5" ^
    --collect-all playwright ^
    --collect-all selenium ^
    --collect-all PyQt5 ^
    --noconfirm ^
    unified_parser.py
```

## Контакты

При возникновении проблем проверьте лог-файл `unified_parser_log.txt` после запуска.
