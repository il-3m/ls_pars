# 📝 Сводка изменений для исправления EXE-сборки парсера

## 🔍 Анализ проблемы

### Почему EXE не работал на других компьютерах:

1. **Режим --onefile и временные папки**
   - PyInstaller распаковывает всё во временную папку `_MEIxxxxx`
   - Playwright не может найти браузеры в этой папке
   - На вашем компьютере работало, т.к. браузеры установлены глобально

2. **Поздняя настройка переменных окружения**
   - `PLAYWRIGHT_BROWSERS_PATH` устанавливалась ПОСЛЕ импорта playwright
   - Это не работало в EXE режиме

3. **Проблемы с импортом модулей**
   - `eis_parser.py` и `link_finder.py` не находились в пути поиска

## ✅ Выполненные исправления

### 1. Обновлён `unified_parser.py`

#### Добавлена функция `setup_playwright_for_exe()`:
- Устанавливает `PLAYWRIGHT_BROWSERS_PATH` ДО импорта playwright
- Использует постоянный кэш `%USERPROFILE%\.cache\ms-playwright`
- Работает как в обычном режиме, так и в EXE

#### Добавлена функция `get_resource_path()`:
- Универсальное получение путей к ресурсам
- Работает в режимах onefile и onedir

#### Улучшен импорт модулей:
- Функция `import_module_from_exe()` для надёжного импорта
- Автоматический поиск модулей в _MEIPASS или рядом с exe

### 2. Создан новый скрипт сборки `build_exe_portable.bat`

**Ключевые особенности:**
- Использует режим `--onedir` (папка) вместо `--onefile`
- Включает `--collect-all=PyQt5` и `--collect-all=playwright`
- Создаёт портативную папку `export\Unified_Parser\`
- Подробные сообщения о процессе сборки

### 3. Создан скрипт установщика `create_installer.iss`

**Для Inno Setup:**
- Профессиональный установщик Windows
- Русская и английская локализация
- Автоматическое создание ярлыков
- Регистрация в системе

### 4. Обновлена документация `README_BUILD_RU.md`

**Содержание:**
- Подробный анализ проблем
- Пошаговые инструкции по сборке
- Решение распространённых ошибок
- Сравнение вариантов распространения

## 📦 Новые файлы

```
/workspace/
├── build_exe_portable.bat      # Новый скрипт сборки (рекомендуется)
├── create_installer.iss        # Скрипт для создания установщика
├── README_BUILD_RU.md          # Обновлённая документация
└── unified_parser.py           # Обновлённый главный файл
```

## 🚀 Как использовать

### Быстрая сборка (рекомендуется):

```cmd
cd /workspace
build_exe_portable.bat
```

**Результат:** `export\Unified_Parser\` (портативная папка)

### Создание установщика:

1. Сначала выполните `build_exe_portable.bat`
2. Установите [Inno Setup](https://jrsoftware.org/isdl.php)
3. Выполните: `iscc create_installer.iss`

**Результат:** `installer_output\UnifiedParser_Setup.exe`

## 🎯 Использование на целевом компьютере

### Портативная версия:
1. Скопируйте папку `Unified_Parser` на целевой ПК
2. Запустите `Unified_Parser.exe`
3. При первом запуске загрузятся браузеры (~150 МБ)

### Установщик:
1. Запустите `UnifiedParser_Setup.exe`
2. Следуйте инструкциям мастера
3. Приложение готово к работе

## 📋 Требования

### Для сборки:
- Windows 10/11
- Python 3.8-3.12
- Интернет (для загрузки зависимостей)

### Для запуска (целевой компьютер):
- Windows 10/11
- Google Chrome (для Selenium)
- Интернет (для первого запуска)
- ❌ Python НЕ требуется!

## ⚠️ Важные замечания

1. **Режим onedir предпочтительнее onefile**
   - Быстрее запуск
   - Надёжнее работа с Playwright
   - Легче отладка

2. **Первый запуск требует интернета**
   - Браузеры Playwright загружаются автоматически
   - Сохраняются в постоянном кэше
   - Последующие запуски работают без интернета

3. **Google Chrome должен быть установлен**
   - Требуется для Selenium части (поиск ссылок)
   - Playwright использует свой Chromium для парсинга

## 🔧 Технические детали

### Изменения в unified_parser.py:

```python
# Ранняя настройка Playwright (ДО импорта)
def setup_playwright_for_exe():
    if getattr(sys, 'frozen', False):
        home_dir = os.path.expanduser("~")
        pw_cache_dir = os.path.join(home_dir, '.cache', 'ms-playwright')
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = pw_cache_dir

pw_cache_path = setup_playwright_for_exe()

# Универсальный импорт модулей
def import_module_from_exe(module_name):
    try:
        return __import__(module_name)
    except ImportError:
        if getattr(sys, 'frozen', False):
            # Поиск в _MEIPASS или рядом с exe
            ...
```

### Директивы PyInstaller:

```cmd
--onedir                    # Папка вместо одного файла
--collect-all=PyQt5         # Все зависимости PyQt5
--collect-all=playwright    # Все зависимости Playwright
--hidden-import=eis_parser  # Явный импорт модулей
--hidden-import=link_finder
```

## ✅ Проверка работоспособности

После сборки проверьте:

1. **Структура папки:**
   ```
   export/Unified_Parser/
   ├── Unified_Parser.exe
   ├── _internal/
   └── requirements.txt
   ```

2. **Запуск на вашем компьютере:**
   ```cmd
   cd export\Unified_Parser
   Unified_Parser.exe
   ```

3. **Тест на чистом компьютере:**
   - Скопируйте папку на компьютер без Python
   - Запустите exe
   - Проверьте работу всех функций

---

**Дата обновления:** Апрель 2026
**Версия:** 1.0
