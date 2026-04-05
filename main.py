import sys
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QProgressBar,
                             QSplitter, QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# --- Модели данных ---

@dataclass
class DrugItem:
    registry_number: str = ""       # Номер РУ
    trade_name: str = ""            # Торговое наименование
    dosage: str = ""                # Дозировка
    form: str = ""                  # Лекарственная форма
    quantity: str = ""              # Количество
    unit: str = ""                  # Ед. изм.
    price: str = ""                 # Цена за ед.
    total_sum: str = ""             # Сумма
    source_url: str = ""            # Источник

    def to_dict(self):
        return asdict(self)

# --- Скрипт парсинга (выполняется в контексте браузера) ---

EXTRACT_SCRIPT = """
() => {
    const results = [];
    
    // Функция для очистки текста
    const clean = (text) => {
        if (!text) return "";
        return text.replace(/\\s+/g, ' ').trim();
    };

    // Функция для поиска значения по метке в соседних элементах или внутри родителя
    const findValueByLabel = (root, labelPatterns) => {
        let text = root.innerText || "";
        
        // Пробуем найти через регулярные выражения в тексте блока
        for (const pattern of labelPatterns) {
            const regex = new RegExp(pattern + '\\\\s*:?\\\\s*([^;\\\\n]+)', 'i');
            const match = text.match(regex);
            if (match && match[1]) {
                return clean(match[1]);
            }
        }
        return "";
    };

    // 1. Парсим основную таблицу контракта (если она есть и раскрыта)
    // Ищем контейнеры строк контракта
    const contractRows = document.querySelectorAll('div.contract-row, tr.data-row, div.list-item');
    
    // Вспомогательная функция для извлечения данных из одной визуальной группы (строка + детали)
    const extractFromGroup = (groupElement) => {
        const item = {
            registry_number: "",
            trade_name: "",
            dosage: "",
            form: "",
            quantity: "",
            unit: "",
            price: "",
            total_sum: ""
        };

        const text = groupElement.innerText;

        // Попытка найти РУ (обычно формат цифровой или буквы+цифры)
        // Паттерн: "Номер РУ" или "Регистрационное удостоверение"
        item.registry_number = findValueByLabel(groupElement, [
            'Номер РУ', 'Регистрационное удостоверение №', 'РУ №', 'Registration No'
        ]);

        // Торговое наименование
        item.trade_name = findValueByLabel(groupElement, [
            'Торговое наименование', 'Наименование лекарства', 'Drug Name'
        ]);

        // Дозировка
        item.dosage = findValueByLabel(groupElement, [
            'Дозировка', 'Dosage', 'Сила действия'
        ]);

        // Форма
        item.form = findValueByLabel(groupElement, [
            'Лекарственная форма', 'Форма выпуска', 'Form'
        ]);

        // Количество
        const qtyMatch = text.match(/(Количество|Qty)\\\\s*:?\\\\s*([0-9.,]+)\\\\s*([а-яA-Za-zё.]+)/i);
        if (qtyMatch) {
            item.quantity = qtyMatch[2];
            item.unit = qtyMatch[3];
        } else {
             // Альтернативный поиск количества
             item.quantity = findValueByLabel(groupElement, ['Количество']);
             item.unit = findValueByLabel(groupElement, ['Ед\\. изм', 'Unit']);
        }

        // Цена
        const priceMatch = text.match(/(Цена|Price)\\\\s*:?\\\\s*([0-9.,]+(?:\\\\s?[рубРURRUB]?))/i);
        if (priceMatch) {
            item.price = priceMatch[2];
        } else {
            item.price = findValueByLabel(groupElement, ['Цена за ед', 'Unit Price']);
        }

        // Сумма
        const sumMatch = text.match(/(Сумма|Total|Стоимость)\\\\s*:?\\\\s*([0-9.,]+(?:\\\\s?[рубРURRUB]?))/i);
        if (sumMatch) {
            item.total_sum = sumMatch[2];
        } else {
            item.total_sum = findValueByLabel(groupElement, ['Сумма', 'Total Sum']);
        }

        // Проверка: если есть хоть название или РУ, считаем это лекарством
        if (item.trade_name || item.registry_number) {
            return item;
        }
        return null;
    };

    // СТРАТЕГИЯ: Ищем все возможные места, где могут быть данные о лекарствах
    
    // Вариант А: Таблицы внутри карточки
    const tables = document.querySelectorAll('table');
    tables.forEach(table => {
        const rows = table.querySelectorAll('tr');
        let headerMap = {};
        
        // Пытаемся определить заголовки
        const firstRow = rows[0];
        if (firstRow) {
            const cells = firstRow.querySelectorAll('th, td');
            cells.forEach((cell, idx) => {
                const txt = clean(cell.innerText).toLowerCase();
                if (txt.includes('ру') || txt.includes('регистрацион')) headerMap['ru'] = idx;
                if (txt.includes('наименован') || txt.includes('торговое')) headerMap['name'] = idx;
                if (txt.includes('дозировк')) headerMap['dosage'] = idx;
                if (txt.includes('форм')) headerMap['form'] = idx;
                if (txt.includes('количеств')) headerMap['qty'] = idx;
                if (txt.includes('цена')) headerMap['price'] = idx;
                if (txt.includes('сумм')) headerMap['sum'] = idx;
                if (txt.includes('ед\\\. изм') || txt.includes('единиц')) headerMap['unit'] = idx;
            });
        }

        // Если нашли заголовки, парсим строки
        if (Object.keys(headerMap).length > 1) {
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const cells = row.querySelectorAll('td');
                if (cells.length < 2) continue;

                const getItemText = (key) => {
                    if (headerMap[key] !== undefined && cells[headerMap[key]]) {
                        return clean(cells[headerMap[key]].innerText);
                    }
                    return "";
                };

                const rName = getItemText('name');
                const rRu = getItemText('ru');
                
                if (rName || rRu) {
                    results.push({
                        registry_number: getItemText('ru'),
                        trade_name: rName,
                        dosage: getItemText('dosage'),
                        form: getItemText('form'),
                        quantity: getItemText('qty'),
                        unit: getItemText('unit'),
                        price: getItemText('price'),
                        total_sum: getItemText('sum')
                    });
                }
            }
        }
    });

    // Вариант Б: Структурированные блоки (div-верстка), часто используется в деталях
    // Ищем блоки, содержащие ключевые слова
    const allDivs = document.querySelectorAll('div');
    const processedGroups = new Set(); // Чтобы не дублировать

    allDivs.forEach(div => {
        const text = div.innerText;
        if ((text.includes('Торговое наименование') || text.includes('Номер РУ')) && !processedGroups.has(div)) {
            // Проверяем, не является ли этот div частью уже обработанной таблицы (чтобы избежать дублей)
            let parentTable = div.closest('table');
            if (parentTable && results.some(r => r.trade_name && text.includes(r.trade_name))) {
                return; // Уже взято из таблицы
            }

            const item = extractFromGroup(div);
            if (item) {
                // Простая проверка на дубликат по РУ+Названию
                const isDuplicate = results.some(r => 
                    r.registry_number === item.registry_number && 
                    r.trade_name === item.trade_name
                );
                if (!isDuplicate) {
                    results.push(item);
                    processedGroups.add(div);
                }
            }
        }
    });

    return results;
}
"""

# --- Воркер парсинга (поток) ---

class ParserWorker(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.progress_signal.emit("Инициализация браузера...")
            with sync_playwright() as p:
                # Запуск браузера
                browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Установка таймаутов
                page.set_default_timeout(60000) 
                page.set_default_navigation_timeout(60000)

                self.progress_signal.emit(f"Загрузка страницы: {self.url}")
                
                try:
                    page.goto(self.url, wait_until="networkidle")
                except PlaywrightTimeout:
                    self.progress_signal.emit("Таймаут загрузки, пробуем парсить то, что есть...")
                
                # Ждем появления контента
                page.wait_for_selector("body", timeout=10000)
                
                self.progress_signal.emit("Анализ структуры страницы...")
                
                # Скроллим страницу, чтобы подгрузить ленивые элементы
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)

                # Раскрытие всех деталей (если есть кнопки "Показать подробности")
                # Попытка кликнуть по всем кнопкам раскрытия
                buttons = page.query_selector_all("button, a.link-detail")
                for btn in buttons:
                    txt = btn.inner_text().lower()
                    if "подробн" in txt or "раскрыть" in txt or "show" in txt:
                        try:
                            btn.click(timeout=2000)
                            page.wait_for_timeout(500)
                        except:
                            pass

                self.progress_signal.emit("Извлечение данных...")
                
                # Выполнение JS скрипта
                data = page.evaluate(EXTRACT_SCRIPT)
                
                self.progress_signal.emit(f"Найдено позиций: {len(data)}")
                
                browser.close()
                
                # Фильтрация пустых результатов
                clean_data = [item for item in data if item.get('trade_name') or item.get('registry_number')]
                
                self.finished_signal.emit(clean_data)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.error_signal.emit(f"Ошибка: {str(e)}\n{error_details}")

# --- GUI Приложение ---

class EISParserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EIS Parser Pro (PyQt6)")
        self.setMinimumSize(800, 600)
        self.current_data = []

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Заголовок
        title = QLabel("Парсер лекарств ЕИС (Zakupki.gov.ru)")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Группа ввода
        input_group = QGroupBox("Параметры запуска")
        input_layout = QFormLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Вставьте ссылку на страницу контракта...")
        self.url_input.setFont(QFont("Consolas", 10))
        
        self.btn_start = QPushButton("Запустить парсинг")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; padding: 10px; 
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_start.clicked.connect(self.start_parsing)

        self.btn_save = QPushButton("Сохранить в Excel")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; padding: 10px; 
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b7dda; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_save.clicked.connect(self.save_to_excel)
        self.btn_save.setEnabled(False)

        input_layout.addRow("URL контракта:", self.url_input)
        input_layout.addRow(self.btn_start)
        input_layout.addRow(self.btn_save)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # Прогресс бар
        self.progress = QProgressBar()
        self.progress.setRange(0, 0) # Бесконечная анимация
        self.progress.hide()
        main_layout.addWidget(self.progress)

        # Лог
        log_group = QGroupBox("Лог операций")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setStyleSheet("background-color: #f5f5f5; color: #333;")
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, stretch=1)

        self.log("Готов к работе. Ожидание ссылки...")

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def start_parsing(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Ошибка", "Введите URL страницы!")
            return

        self.btn_start.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.progress.show()
        self.log_output.clear()
        self.log(f"Запуск парсинга для: {url}")

        self.worker = ParserWorker(url)
        self.worker.progress_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_parsing_finished)
        self.worker.error_signal.connect(self.on_parsing_error)
        self.worker.start()

    def on_parsing_finished(self, data: list):
        self.progress.hide()
        self.btn_start.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.current_data = data
        
        self.log(f"Успешно завершено! Найдено записей: {len(data)}")
        if len(data) == 0:
            QMessageBox.warning(self, "Внимание", "Данные не найдены. Проверьте структуру страницы или ссылку.")
        else:
            # Предпросмотр в логе
            self.log("--- Первые 3 результата ---")
            for i, item in enumerate(data[:3]):
                self.log(f"{i+1}. {item.get('trade_name', 'N/A')} ({item.get('registry_number', 'N/A')})")

    def on_parsing_error(self, error_msg: str):
        self.progress.hide()
        self.btn_start.setEnabled(True)
        self.log("КРИТИЧЕСКАЯ ОШИБКА:")
        self.log(error_msg)
        QMessageBox.critical(self, "Ошибка парсинга", f"Произошла ошибка:\n{error_msg}")

    def save_to_excel(self):
        if not self.current_data:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить результат", 
            f"drugs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
            "Excel Files (*.xlsx)"
        )

        if file_path:
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Лекарства"

                headers = ["№", "Номер РУ", "Торговое наименование", "Дозировка", "Форма", "Количество", "Ед. изм.", "Цена", "Сумма", "Источник"]
                ws.append(headers)

                for idx, item in enumerate(self.current_data, 1):
                    row = [
                        idx,
                        item.get('registry_number', ''),
                        item.get('trade_name', ''),
                        item.get('dosage', ''),
                        item.get('form', ''),
                        item.get('quantity', ''),
                        item.get('unit', ''),
                        item.get('price', ''),
                        item.get('total_sum', ''),
                        item.get('source_url', self.url_input.text())
                    ]
                    ws.append(row)

                # Автоширина колонок
                for col in ws.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    ws.column_dimensions[column].width = min(adjusted_width, 50)

                wb.save(file_path)
                self.log(f"Файл успешно сохранен: {file_path}")
                QMessageBox.information(self, "Готово", f"Данные сохранены в:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось сохранить файл:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Стиль приложения (опционально)
    app.setStyle("Fusion")
    window = EISParserApp()
    window.show()
    sys.exit(app.exec())
