# Инструкция по сборке EXE-файла

## Вариант 1: Автоматическая сборка (рекомендуется)

1. Откройте командную строку Windows (cmd)
2. Перейдите в папку с проектом:
   ```
   cd путь\к\папке\с\проектом
   ```
3. Запустите скрипт сборки:
   ```
   build_exe.bat
   ```
4. Дождитесь завершения сборки
5. Готовый EXE-файл будет находиться в папке `dist\LS_Parser_Light.exe`

## Вариант 2: Ручная сборка

Если автоматический скрипт не работает, выполните команды вручную:

### Шаг 1: Установите Python
Скачайте и установите Python с официального сайта: https://www.python.org/downloads/
При установке обязательно отметьте галочку "Add Python to PATH"

### Шаг 2: Установите зависимости
Откройте командную строку и выполните:
```bash
pip install pyinstaller pandas PyQt5 selenium webdriver-manager requests openpyxl
```

### Шаг 3: Соберите EXE
Выполните команду:
```bash
pyinstaller --onefile --windowed --name "LS_Parser_Light" --hidden-import=pandas --hidden-import=PyQt5 --hidden-import=selenium --hidden-import=webdriver_manager --hidden-import=requests --hidden-import=openpyxl "ЛС-парсер-лайт.py"
```

### Шаг 4: Найдите готовый файл
Готовый EXE-файл будет в папке `dist\LS_Parser_Light.exe`

## Использование

Скопируйте файл `LS_Parser_Light.exe` на любой компьютер с Windows 10/11 и запустите его двойным кликом. Никаких дополнительных программ устанавливать не нужно!

## Примечания

- Размер EXE-файла будет около 150-200 МБ, так как он включает все необходимые библиотеки
- Первый запуск может занять несколько секунд
- Для работы парсера потребуется установленный Google Chrome или Chromium
