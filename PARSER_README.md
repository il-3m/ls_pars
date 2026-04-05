# EIS Production Parser (Python)

Скрипт: `eis_parser.py`

Для запуска без ручных команд есть GUI-режим (`--gui`) и файл `run_parser_gui.bat`.

## Что делает

- Открывает карточку контракта ЕИС
- Находит блок `Объекты закупки`
- Раскрывает вложенные строки
- Парсит поля в колонки:
  - Наименование
  - Категории ЛС
  - ОКПД2
  - Страна происхождения
  - МНН (ГРЛС)
  - Торговое наименование
  - РУ
  - Форма выпуска
  - Дозировка
  - Количество в потреб. единице
  - Цена за единицу товара
  - Сумма, руб
- Сохраняет отладочный архив: HTML, JSON, скриншоты ошибок

## Установка

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install playwright pandas openpyxl
playwright install chromium
```

`pandas/openpyxl` нужны только для `.xlsx`. CSV работает и без них.

## Запуск (одна ссылка)

```bash
python eis_parser.py \
  --url "https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html?reestrNumber=2312813818126000251&contractInfoId=108730614" \
  --archive-dir archive \
  --out-csv export/result.csv \
  --out-xlsx export/result.xlsx \
  --trace
```

## Единый интерфейс (без сборки команд)

### Вариант 1: двойной клик

1. Откройте папку проекта.
2. Запустите `run_parser_gui.bat`.
3. В окне укажите ссылку и слово для поиска.
4. Нажмите `Запустить парсинг`.

### Вариант 2: через Python

```bash
python eis_parser.py --gui
```

GUI сам запускает парсинг, показывает лог и таблицу результатов. После выполнения можно открыть CSV кнопкой `Открыть CSV`.

## Пакетный запуск

1. Создайте файл `urls.txt`, по одной ссылке на строку.
2. Запустите:

```bash
python eis_parser.py --url-file urls.txt --archive-dir archive --out-csv export/all.csv --out-xlsx export/all.xlsx
```

## Что делать с архивом

- `archive/job_*/raw/objects_frame.html` - HTML для offline-диагностики
- `archive/job_*/parsed/rows.json` - результат до экспорта
- `archive/failures/*.png` и `*.txt` - скриншоты и ошибки
- `archive/trace_*.zip` - Playwright trace для разбора нестабильных случаев

Если нужно, можно добавить отдельный режим offline, который парсит `objects_frame.html` без браузера.