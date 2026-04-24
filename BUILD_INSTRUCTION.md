# Инструкция по созданию EXE файла для Unified Parser

## Требования

Для создания EXE файла вам понадобится компьютер с:
- Windows 10/11
- Установленным Python 3.8+
- Установленным Google Chrome
- Подключением к интернету

## Автоматическая сборка (рекомендуется)

### Вариант 1: Простая сборка (один файл)

1. Запустите файл `build_exe_simple.bat` двойным кликом
2. Дождитесь завершения процесса сборки
3. Готовый EXE файл будет находиться в папке `dist/UnifiedParser_Release/`

**Этот вариант рекомендуется** - создается один EXE файл, который удобно распространять.

### Вариант 2: Полная сборка со spec-файлом

1. Запустите файл `build_exe.bat` двойным кликом
2. Дождитесь завершения процесса сборки
3. Готовые файлы будут находиться в папке `dist/UnifiedParser/`

## Ручная сборка

Если автоматическая сборка не работает, выполните следующие шаги вручную:

### Шаг 1: Установка зависимостей

```bash
pip install PyQt5 selenium webdriver-manager playwright pandas openpyxl pyinstaller
```

### Шаг 2: Установка браузеров Playwright

```bash
playwright install chromium
```

### Шаг 3: Сборка EXE файла

```bash
pyinstaller unified_parser.spec --clean
```

Или используйте команду без spec-файла:

```bash
pyinstaller --onefile --windowed --name UnifiedParser ^
    --hidden-import=PyQt5 ^
    --hidden-import=selenium ^
    --hidden-import=webdriver_manager ^
    --hidden-import=playwright ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=eis_parser ^
    --add-data "eis_parser.py;." ^
    --add-data "link_finder.py;." ^
    unified_parser.py
```

### Шаг 4: Проверка результата

Готовый EXE файл будет находиться в папке `dist/UnifiedParser.exe` (при использовании --onefile)
или в папке `dist/UnifiedParser/` (при использовании spec-файла).

## Распространение

### Вариант 1: One-file режим (один файл)

Если вы использовали флаг `--onefile`:
- Скопируйте `dist/UnifiedParser.exe` на целевой компьютер
- Убедитесь, что на целевом компьютере установлен Google Chrome
- Запустите EXE файл

### Вариант 2: One-folder режим (папка с файлами)

Если вы использовали spec-файл или `--onedir`:
- Скопируйте всю папку `dist/UnifiedParser/` на целевой компьютер
- Убедитесь, что на целевом компьютере установлен Google Chrome
- Запустите `UnifiedParser.exe` из этой папки

## Требования к целевому компьютеру

На компьютере, где будет запускаться EXE файл, должно быть установлено:

1. **Windows 10/11** (64-бит)
2. **Google Chrome** - необходим для работы Selenium
   - Скачать: https://www.google.com/chrome/
3. **Доступ в интернет** - для подключения к zakupki.gov.ru

## Возможные проблемы и решения

### Ошибка: "Chrome not reachable"

**Решение:** Убедитесь, что Google Chrome установлен и доступен в PATH.

### Ошибка: "Playwright browser not found"

**Решение:** Установите браузеры Playwright командой:
```bash
playwright install chromium
```

Или скопируйте папку с браузерами из системы разработчика:
```
C:\Users\<User>\AppData\Local\ms-playwright\
```

### Ошибка: "Module not found"

**Решение:** При сборке убедитесь, что все зависимости указаны в spec-файле или через флаги `--hidden-import`.

### Большой размер EXE файла

EXE файл может занимать 100-200 МБ из-за включения:
- PyQt5 (библиотека интерфейса)
- Playwright с браузерами
- Pandas и других библиотек

Это нормально для автономного приложения.

## Примечания

1. **Антивирусы**: Некоторые антивирусы могут ложно определять EXE файлы от PyInstaller как угрозу. Добавьте исключение или подпишите файл цифровой подписью.

2. **Первый запуск**: При первом запуске WebDriver Manager может загружать ChromeDriver. Это требует подключения к интернету.

3. **Логи**: Логи работы парсера сохраняются в файле `unified_parser_log.txt` в той же папке, откуда запущен EXE файл.

4. **Обновление**: Для обновления парсера нужно заново собрать EXE файл из исходного кода.
