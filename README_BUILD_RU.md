# 🚀 Unified Parser - Инструкция по созданию портативной версии

## ❗ Почему предыдущие версии EXE не работали на других компьютерах

### Основные проблемы:

1. **Режим onefile и временные папки**
   - При сборке `--onefile` PyInstaller распаковывает всё во временную папку `_MEIxxxxx`
   - Playwright ищет браузеры в этой временной папке, но они там не находятся
   - На вашем компьютере работает, потому что браузеры установлены глобально

2. **Отсутствие переменных окружения**
   - Переменная `PLAYWRIGHT_BROWSERS_PATH` должна быть установлена ДО импорта playwright
   - В старых версиях это делалось после импорта, что не работало

3. **Неправильные пути к ресурсам**
   - Модули `eis_parser.py` и `link_finder.py` не находились в пути поиска
   - Нужны правильные `--hidden-import` и `--add-data` директивы

4. **Браузеры Playwright не включены**
   - Браузеры (~150 МБ) должны быть либо встроены, либо загружаться при первом запуске
   - В режиме onefile встраивание приводит к огромному размеру и проблемам с путями

## ✅ Решение: Портативная папка вместо одного EXE

### Преимущества режима onedir (папка):

- ✅ **Быстрый запуск** - не распаковывает во временную папку
- ✅ **Надёжная работа с Playwright** - браузеры в постоянном кэше
- ✅ **Легче отладка** - видно структуру приложения
- ✅ **Меньше размер** - не дублирует файлы при каждом запуске

### Недостатки:

- ⚠️ Нужно копировать всю папку, а не один файл
- ⚠️ Пользователь может случайно удалить файлы

## 🔨 Сборка портативной версии

### Вариант 1: Использование готового скрипта (рекомендуется)

```cmd
build_exe_portable.bat
```

Этот скрипт автоматически:
1. Проверит наличие Python
2. Установит все зависимости
3. Скачает браузеры Playwright
4. Соберёт приложение в режиме onedir
5. Скопирует результат в папку `export\Unified_Parser\`

### Вариант 2: Ручная сборка

```cmd
# Установка зависимостей
pip install -r requirements.txt

# Установка браузеров Playwright
python -m playwright install chromium

# Сборка
pyinstaller --noconfirm ^
    --onedir ^
    --windowed ^
    --name "Unified_Parser" ^
    --add-data "requirements.txt;." ^
    --hidden-import=pkg_resources.py2_warn ^
    --hidden-import=selenium ^
    --hidden-import=webdriver_manager ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=playwright ^
    --hidden-import=eis_parser ^
    --hidden-import=link_finder ^
    --collect-all=PyQt5 ^
    --collect-all=playwright ^
    "unified_parser.py"
```

## 📦 Что получается после сборки

```
export/
└── Unified_Parser/
    ├── Unified_Parser.exe      # Главный исполняемый файл
    ├── _internal/               # Внутренние файлы приложения
    │   ├── base_library.zip
    │   ├── eis_parser.cpython-312.pyc
    │   ├── link_finder.cpython-312.pyc
    │   ├── playwright/          # Драйверы Playwright
    │   └── ... другие файлы
    └── requirements.txt
```

## 🎯 Использование на другом компьютере

### Требования:
✅ **Нужно:**
- Windows 10/11
- Google Chrome (для Selenium части - поиск ссылок)
- Интернет (для первого запуска + парсинга)

❌ **НЕ нужно:**
- Python
- Ручная установка зависимостей
- Какие-либо настройки

### Пошаговая инструкция:

1. **Скопируйте папку**
   ```
   Скопируйте ВСЮ папку "Unified_Parser" на целевой компьютер
   Например, в C:\Programs\Unified_Parser\
   ```

2. **Запустите приложение**
   ```
   Дважды кликните на Unified_Parser.exe
   ```

3. **Первый запуск (1-2 минуты)**
   - Playwright проверит наличие браузеров
   - Если браузеров нет, автоматически скачает Chromium (~150 МБ)
   - Сохранит в `%USERPROFILE%\.cache\ms-playwright`
   - Продолжит работу парсера

4. **Последующие запуски**
   - Браузеры уже в кэше
   - Запуск мгновенный
   - Никаких дополнительных загрузок

## 🔧 Создание установщика (опционально)

Если вы хотите создать настоящий установщик (setup.exe):

### Использование Inno Setup:

1. Установите [Inno Setup](https://jrsoftware.org/isdl.php)

2. Создайте файл `installer.iss`:

```iss
[Setup]
AppName=Unified Parser
AppVersion=1.0
DefaultDirName={pf}\UnifiedParser
DefaultGroupName=Unified Parser
OutputDir=installer_output
OutputBaseFilename=UnifiedParser_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "export\Unified_Parser\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\Unified Parser"; Filename: "{app}\Unified_Parser.exe"
Name: "{commondesktop}\Unified Parser"; Filename: "{app}\Unified_Parser.exe"

[Run]
Filename: "{app}\Unified_Parser.exe"; Description: "Запустить Unified Parser"; Flags: nowait postinstall skipifsilent
```

3. Скомпилируйте:
   ```cmd
   iscc installer.iss
   ```

4. Готовый установщик будет в папке `installer_output\`

## ⚠️ Возможные проблемы и решения

### 1. Ошибка: "ModuleNotFoundError: No module named 'eis_parser'"

**Решение:** Убедитесь, что используются правильные `--hidden-import`:
```cmd
--hidden-import=eis_parser --hidden-import=link_finder
```

### 2. Ошибка: "Executable doesn't exist at ... playright\\driver\\chromium..."

**Причина:** Браузеры Playwright не найдены

**Решение:**
- Дождитесь завершения автозагрузки браузеров при первом запуске
- Или предварительно установите браузеры:
  ```cmd
  python -m playwright install chromium
  ```

### 3. Ошибка: "DLL load failed" или "ImportError"

**Причина:** Не хватает библиотек Visual C++ Redistributable

**Решение:**
- Установите [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### 4. Антивирус блокирует приложение

**Причина:** Ложное срабатывание на PyInstaller

**Решение:**
- Добавьте папку приложения в исключения антивируса
- Или подпишите приложение цифровым сертификатом

### 5. Приложение запускается и сразу закрывается

**Решение:**
- Запустите из командной строки для просмотра ошибок:
  ```cmd
  cd "path\to\Unified_Parser"
  Unified_Parser.exe
  ```
- Проверьте логи в файле `unified_parser_log.txt`

## 📊 Сравнение режимов

| Параметр | onefile (один EXE) | onedir (папка) |
|----------|-------------------|----------------|
| Размер на диске | ~50 МБ (сжатый) | ~200-300 МБ |
| Время запуска | Медленно (распаковка) | Быстро |
| Работа с Playwright | Проблематично | Надёжно |
| Удобство распространения | Один файл | Папка |
| Отладка | Сложно | Легко |
| **Рекомендация** | ❌ Не рекомендуется | ✅ Рекомендуется |

## 🆘 Поддержка

Если проблемы не решаются:

1. Проверьте версию Python: `python --version` (должна быть 3.8-3.12)
2. Обновите pip: `python -m pip install --upgrade pip`
3. Попробуйте собрать заново после очистки:
   ```cmd
   rmdir /s /q build dist
   del *.spec
   build_exe_portable.bat
   ```
4. Запустите из командной строки для просмотра ошибок

---

**Удачи с использованием парсера! 🎉**
