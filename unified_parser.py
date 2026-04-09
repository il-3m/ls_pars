#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified parser that combines link finding and parsing into a single workflow.
Workflow:
1. Search for contract links using Selenium
2. For each link found, parse it using Playwright
3. Accumulate all parsed data into a single table
4. Export the final result as CSV/XLSX
"""

import sys
import os

# Mock tkinter if not available (for headless environments)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    # Create mocks for tkinter
    class MockTk:
        pass
    class MockTtk:
        pass
    class MockMessageBox:
        @staticmethod
        def showinfo(title, message): print(f"[INFO] {title}: {message}")
        @staticmethod
        def showwarning(title, message): print(f"[WARNING] {title}: {message}")
        @staticmethod
        def showerror(title, message): print(f"[ERROR] {title}: {message}")
        @staticmethod
        def about(parent, title, message): print(f"[ABOUT] {title}: {message}")
    
    tk = type(sys)('tkinter_mock')
    tk.Tk = MockTk
    tk.ttk = MockTtk
    tk.messagebox = MockMessageBox
    tk.filedialog = type(sys)('filedialog_mock')
    sys.modules['tkinter'] = tk
    sys.modules['tkinter.ttk'] = MockTtk
    sys.modules['tkinter.messagebox'] = MockMessageBox
    sys.modules['tkinter.filedialog'] = sys.modules['tkinter.filedialog'] if 'tkinter.filedialog' in sys.modules else type(sys)('filedialog')
    
    ttk = MockTtk
    messagebox = MockMessageBox
    filedialog = sys.modules.get('tkinter.filedialog', type(sys)('filedialog'))

import time
import logging
import argparse
import asyncio
import csv
import re
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QDateEdit, QMessageBox, QProgressBar,
    QHBoxLayout, QTextEdit, QFileDialog, QDialog,
    QGridLayout, QSpacerItem, QSizePolicy,
    QComboBox, QCompleter, QFormLayout, QStatusBar,
    QListWidget, QListWidgetItem, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QTabWidget
)
from PyQt5.QtCore import QDate, Qt, QThread, pyqtSignal, QStringListModel, QUrl
from PyQt5.QtGui import QColor, QDesktopServices
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from playwright.async_api import Browser, BrowserContext, Error, Frame, Page, async_playwright

# Import parsing logic from eis_parser
from eis_parser import (
    FIELD_ORDER, EXPORT_HEADERS_RU, ParseRecord, EISParser,
    export_csv, export_xlsx, _clean, build_arg_parser
)

# Настройка логирования
logging.basicConfig(
    filename='unified_parser_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


class UnifiedParserWorker(QThread):
    """Поток для полного цикла: поиск ссылок + парсинг"""
    update_progress = pyqtSignal(int)
    update_output = pyqtSignal(str)
    link_found = pyqtSignal(str)
    row_parsed = pyqtSignal(dict)  # отправляет каждую строку данных
    data_parsed = pyqtSignal(int)  # количество строк добавлено
    finished = pyqtSignal(list)
    
    def __init__(self, search_text, date_from, date_to, moscow_only, rosunimed_only, 
                 max_contracts, archive_dir, out_csv, out_xlsx, headed, trace,
                 timeout_ms, expand_rounds, page_load_delay, expand_delay):
        super().__init__()
        self.search_text = search_text
        self.date_from = date_from
        self.date_to = date_to
        self.moscow_only = moscow_only
        self.rosunimed_only = rosunimed_only
        self.max_contracts = max_contracts
        self.archive_dir = archive_dir
        self.out_csv = out_csv
        self.out_xlsx = out_xlsx
        self.headed = headed
        self.trace = trace
        self.timeout_ms = timeout_ms
        self.expand_rounds = expand_rounds
        self.page_load_delay = page_load_delay
        self.expand_delay = expand_delay
        self.driver = None
        self.found_links = []
        self.all_rows = []

    def run(self):
        try:
            # Шаг 1: Поиск ссылок
            self.update_output.emit("=== Этап 1: Поиск ссылок ===")
            links = self.find_links()
            
            if not links:
                self.update_output.emit("Ссылки не найдены!")
                self.finished.emit([])
                return
            
            self.update_output.emit(f"Найдено ссылок: {len(links)}")
            
            # Шаг 2: Парсинг каждой ссылки
            self.update_output.emit("=== Этап 2: Парсинг данных ===")
            self.parse_all_links(links)
            
            self.update_output.emit(f"Всего обработано строк: {len(self.all_rows)}")
            self.finished.emit(self.all_rows)
            
        except Exception as e:
            self.update_output.emit(f"Ошибка: {str(e)}")
            logging.error(f"Ошибка в потоке: {str(e)}", exc_info=True)
        finally:
            if self.driver:
                self.driver.quit()

    def find_links(self):
        """Поиск ссылок на контракты (из link_finder.py)"""
        base_url = "https://zakupki.gov.ru/epz/contract/search/results.html"
        params = {
            "searchString": self.search_text,
            "morphology": "on",
            "search-filter": "Дате+размещения",
            "fz44": "on",
            "contractStageList_1": "on",
            "contractStageData": "1",
            "budgetLevelsIdNameHidden": "{}",
            "contractDateFrom": self.date_from,
            "contractDateTo": self.date_to,
            "sortBy": "UPDATE_DATE",
            "pageNumber": "1",
            "sortDirection": "false",
            "recordsPerPage": "_10",
            "showLotsInfoHidden": "false",
            "strictEqual": "true"
        }

        if self.rosunimed_only:
            params["customerIdOrg"] = '14269:ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ ВЫСШЕГО ОБРАЗОВАНИЯ "РОССИЙСКИЙ УНИВЕРСИТЕТ МЕДИЦИНЫ" МИНИСТЕРСТВА ЗДРАВООХРАНЕНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИzZ03731000459zZ666998zZ63203zZ7707082145zZ'
        elif self.moscow_only:
            params["customerPlace"] = "77000000000,50000000000"
            params["customerPlaceCodes"] = "77000000000,50000000000"

        url = base_url + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        self.update_output.emit(f"Запрос: {url}")
        self.update_progress.emit(5)

        # Инициализация WebDriver
        chrome_options = Options()
        if not self.headed:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-gcm")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # Загрузка первой страницы
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.driver.get(url)
                self.update_output.emit("Ожидание загрузки страницы...")
                self.update_progress.emit(10)
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href]"))
                )
                break
            except Exception as e:
                self.update_output.emit(f"Попытка {attempt + 1}/{max_attempts} не удалась: {str(e)}")
                if attempt == max_attempts - 1:
                    raise Exception("Не удалось загрузить страницу")
                time.sleep(3)

        # Определение общего числа страниц
        try:
            pagination = self.driver.find_elements(By.CSS_SELECTOR, ".paginator a")
            page_numbers = []
            for a in pagination:
                try:
                    page_numbers.append(int(a.text))
                except ValueError:
                    continue
            total_pages = max(page_numbers) if page_numbers else 1
            self.update_output.emit(f"Всего страниц: {total_pages}")
        except Exception:
            total_pages = 1
            self.update_output.emit("Не удалось определить количество страниц, используем 1")

        all_links = set()
        contracts_count = 0

        # Цикл по страницам результатов
        for page in range(1, total_pages + 1):
            if contracts_count >= self.max_contracts:
                break

            params["pageNumber"] = str(page)
            url = base_url + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            self.driver.get(url)
            self.update_output.emit(f"Страница {page}/{total_pages}")
            progress = 10 + int((page / total_pages) * 20)
            self.update_progress.emit(progress)

            # Извлечение всех ссылок
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
            original_links = [
                link.get_attribute("href")
                for link in links
                if link.get_attribute("href") and "contract/contractCard/common-info.html" in link.get_attribute("href")
            ]
            
            unique_links = list(set(original_links))
            self.update_output.emit(f"Найдено уникальных ссылок на странице: {len(unique_links)}")

            for i, original_link in enumerate(unique_links, 1):
                if contracts_count >= self.max_contracts:
                    break

                # Проверка на CAPTCHA
                if "captcha" in self.driver.page_source.lower():
                    self.update_output.emit("Обнаружена CAPTCHA!")
                    time.sleep(2)

                # Преобразование ссылки в целевой формат
                target_link = original_link.replace("common-info.html", "payment-info-and-target-of-order.html")
                
                # Извлечение номера реестра
                reestr_match = re.search(r'reestrNumber=([0-9]+)', target_link)
                if reestr_match:
                    reestr_number = reestr_match.group(1)
                    final_link = f"https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html?reestrNumber={reestr_number}"
                else:
                    final_link = target_link

                all_links.add(final_link)
                contracts_count += 1
                self.link_found.emit(final_link)
                self.update_output.emit(f"Найдено контрактов: {contracts_count}/{self.max_contracts}")

        self.found_links = list(all_links)
        return self.found_links

    def parse_all_links(self, links: List[str]):
        """Парсинг всех ссылок и накопление данных"""
        parser = EISParser(
            timeout_ms=self.timeout_ms,
            expand_rounds=self.expand_rounds,
            page_load_delay=self.page_load_delay,
            expand_delay=self.expand_delay,
        )
        archive_dir = Path(self.archive_dir)
        
        async def parse_batch():
            async with async_playwright() as p:
                browser: Browser = await p.chromium.launch(headless=not self.headed)
                context: BrowserContext = await browser.new_context(locale="ru-RU")
                
                for idx, url in enumerate(links, start=1):
                    self.update_output.emit(f"[{idx}/{len(links)}] Обработка: {url}")
                    progress = 30 + int((idx / len(links)) * 60)
                    self.update_progress.emit(progress)
                    
                    page = await context.new_page()
                    try:
                        rows = await parser.parse_url(page, url, archive_dir=archive_dir, save_trace=self.trace)
                        self.all_rows.extend(rows)
                        # Отправляем каждую строку для отображения в таблице
                        for row in rows:
                            self.row_parsed.emit(row)
                        self.data_parsed.emit(len(rows))
                        self.update_output.emit(f"  -> добавлено строк: {len(rows)}, всего: {len(self.all_rows)}")
                    except Exception as exc:
                        self.update_output.emit(f"  -> ошибка: {exc}")
                        logging.error(f"Ошибка парсинга {url}: {exc}")
                    finally:
                        await page.close()
                
                await context.close()
                await browser.close()
        
        asyncio.run(parse_batch())
        
        # Экспорт результатов
        if self.all_rows:
            csv_path = Path(self.out_csv)
            export_csv(self.all_rows, csv_path)
            self.update_output.emit(f"CSV сохранен: {csv_path}")
            
            if self.out_xlsx:
                ok = export_xlsx(self.all_rows, Path(self.out_xlsx))
                if ok:
                    self.update_output.emit(f"XLSX сохранен: {self.out_xlsx}")


class UnifiedParserApp(QMainWindow):
    """Основное приложение объединенного парсера"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.thread = None
        self.all_rows = []

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle('Универсальный парсер ЕИС (Поиск + Парсинг)')
        self.setGeometry(100, 100, 1600, 1000)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный горизонтальный layout: слева панель управления, справа таблица
        main_hlayout = QHBoxLayout()
        main_hlayout.setSpacing(0)
        main_hlayout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            QMainWindow { background-color: #ffffff; }
            QLabel { font-size: 12px; font-weight: normal; color: #000000; }
            QLineEdit, QDateEdit, QComboBox { 
                font-size: 12px; padding: 6px; 
                border: 1px solid #cccccc; 
                background-color: white;
            }
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
                border: 1px solid #000000;
            }
            QPushButton { 
                font-size: 12px; font-weight: bold; padding: 8px 16px; 
                background-color: #ffffff; color: #000000; 
                border: 1px solid #000000; 
            }
            QPushButton:hover { background-color: #f0f0f0; }
            QPushButton:disabled { background-color: #e0e0e0; color: #999999; }
            QPushButton#stopButton { border: 1px solid #000000; }
            QCheckBox { font-size: 12px; color: #000000; spacing: 6px; }
            QProgressBar { 
                border: 1px solid #cccccc; 
                text-align: center; font-size: 10px; font-weight: bold;
                background-color: #ffffff;
            }
            QProgressBar::chunk { background-color: #000000; }
            QTextEdit { 
                font-size: 10px; border: 1px solid #cccccc; 
                background-color: white; font-family: 'Consolas', monospace;
            }
            QTabWidget::pane { 
                border: 1px solid #cccccc; 
                background-color: white; 
            }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab { 
                background-color: #ffffff; 
                color: #000000; 
                padding: 8px 16px; 
                margin-right: 2px;
                border: 1px solid #cccccc;
                border-bottom: none;
                font-weight: normal;
            }
            QTabBar::tab:selected { 
                background-color: #ffffff; 
                color: #000000;
                border-bottom: 1px solid #ffffff;
            }
            QTabBar::tab:hover:!selected { background-color: #f5f5f5; }
            QTableWidget { 
                font-size: 11px; 
                border: 1px solid #cccccc; 
                background-color: white;
                gridline-color: #dddddd;
            }
            QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #eeeeee; }
            QTableWidget::item:hover { background-color: #f5f5f5; }
            QHeaderView::section { 
                background-color: #ffffff; 
                color: #000000; 
                padding: 8px; 
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 11px;
            }
            QHeaderView::section:hover { background-color: #f0f0f0; }
            QScrollArea { border: none; background-color: transparent; }
            QSplitter::handle { background-color: #cccccc; width: 4px; }
            QStatusBar { 
                background-color: #ffffff; 
                color: #000000; 
                font-size: 11px;
                padding: 4px;
                border-top: 1px solid #cccccc;
            }
        """)

        # === ЛЕВАЯ ПАНЕЛЬ УПРАВЛЕНИЯ (280px) ===
        left_panel = QWidget()
        left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Заголовок
        title_label = QLabel("ПАРАМЕТРЫ ПОИСКА")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        left_layout.addWidget(title_label)

        # Вкладки для разделения настроек
        tab_widget = QTabWidget()
        
        # === ВКЛАДКА 1: ОСНОВНАЯ ===
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout()
        main_tab_layout.setSpacing(12)
        main_tab_layout.setContentsMargins(5, 10, 5, 10)

        # Поисковый запрос
        search_label = QLabel("Поисковый запрос (МНН):")
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setPlaceholderText('Например: АЗИТРОМИЦИН')
        self.search_input.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.search_input.setInsertPolicy(QComboBox.NoInsert)
        main_tab_layout.addWidget(search_label)
        main_tab_layout.addWidget(self.search_input)

        # Даты
        date_layout = QHBoxLayout()
        date_layout.setSpacing(8)
        
        date_from_label = QLabel("Дата с:")
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet("min-width: 110px;")
        
        date_to_label = QLabel("Дата по:")
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet("min-width: 110px;")
        
        date_layout.addWidget(date_from_label)
        date_layout.addWidget(self.date_from)
        date_layout.addWidget(date_to_label)
        date_layout.addWidget(self.date_to)
        main_tab_layout.addLayout(date_layout)

        # Макс. контрактов
        max_contracts_label = QLabel("Макс. контрактов:")
        self.max_contracts_input = QLineEdit()
        self.max_contracts_input.setText("20")
        self.max_contracts_input.setStyleSheet("min-width: 60px;")
        main_tab_layout.addWidget(max_contracts_label)
        main_tab_layout.addWidget(self.max_contracts_input)

        # Фильтры
        filter_group = QLabel()
        filter_group.setStyleSheet("border: 1px solid #cccccc; padding: 8px;")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(6)
        
        self.region_checkbox = QCheckBox('Только Москва и МО')
        self.rosunimed_checkbox = QCheckBox('Только Росунимед')
        self.region_checkbox.toggled.connect(lambda: self.on_checkbox_toggled('region'))
        self.rosunimed_checkbox.toggled.connect(lambda: self.on_checkbox_toggled('rosunimed'))
        
        filter_layout.addWidget(self.region_checkbox)
        filter_layout.addWidget(self.rosunimed_checkbox)
        filter_group.setLayout(filter_layout)
        main_tab_layout.addWidget(filter_group)

        # Кнопка запуска
        self.start_button = QPushButton('ЗАПУСТИТЬ ПОИСК')
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self.start_parsing)
        main_tab_layout.addWidget(self.start_button)

        # Кнопка стоп
        self.stop_button = QPushButton('СТОП')
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(35)
        self.stop_button.clicked.connect(self.stop_parsing)
        main_tab_layout.addWidget(self.stop_button)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(20)
        main_tab_layout.addWidget(self.progress_bar)

        main_tab_layout.addStretch()
        main_tab.setLayout(main_tab_layout)
        tab_widget.addTab(main_tab, "Основная")

        # === ВКЛАДКА 2: НАСТРОЙКИ ===
        settings_tab = QWidget()
        settings_tab_layout = QVBoxLayout()
        settings_tab_layout.setSpacing(10)
        settings_tab_layout.setContentsMargins(5, 8, 5, 8)

        # Таймауты и задержки
        timing_group = QLabel("Таймауты и задержки")
        timing_group.setStyleSheet("font-weight: bold; border: 1px solid #cccccc; padding: 8px;")
        timing_layout = QFormLayout()
        timing_layout.setSpacing(6)
        
        self.timeout_ms_input = QLineEdit()
        self.timeout_ms_input.setText("90000")
        self.expand_rounds_input = QLineEdit()
        self.expand_rounds_input.setText("5")
        self.page_load_delay_input = QLineEdit()
        self.page_load_delay_input.setText("1200")
        self.expand_delay_input = QLineEdit()
        self.expand_delay_input.setText("800")
        
        timing_layout.addRow("Таймаут (мс):", self.timeout_ms_input)
        timing_layout.addRow("Раунды раскрытия:", self.expand_rounds_input)
        timing_layout.addRow("Задержка загрузки (мс):", self.page_load_delay_input)
        timing_layout.addRow("Задержка раскрытия (мс):", self.expand_delay_input)
        
        timing_group_layout = QVBoxLayout()
        timing_group_layout.addLayout(timing_layout)
        timing_group.setLayout(timing_group_layout)
        settings_tab_layout.addWidget(timing_group)

        # Пути к файлам
        paths_group = QLabel("Пути к файлам")
        paths_group.setStyleSheet("font-weight: bold; border: 1px solid #cccccc; padding: 8px;")
        paths_layout = QFormLayout()
        paths_layout.setSpacing(6)
        
        self.archive_dir_input = QLineEdit()
        self.archive_dir_input.setText("archive")
        self.csv_file_input = QLineEdit()
        self.csv_file_input.setText("export/unified_result.csv")
        self.xlsx_file_input = QLineEdit()
        self.xlsx_file_input.setText("export/unified_result.xlsx")
        
        paths_layout.addRow("Папка архива:", self.archive_dir_input)
        paths_layout.addRow("CSV файл:", self.csv_file_input)
        paths_layout.addRow("XLSX файл:", self.xlsx_file_input)
        
        paths_group_layout = QVBoxLayout()
        paths_group_layout.addLayout(paths_layout)
        paths_group.setLayout(paths_group_layout)
        settings_tab_layout.addWidget(paths_group)

        settings_tab_layout.addStretch()
        settings_tab.setLayout(settings_tab_layout)
        tab_widget.addTab(settings_tab, "Настройки")

        left_layout.addWidget(tab_widget)

        # Статистика
        stats_group = QLabel()
        stats_group.setStyleSheet("border: 1px solid #cccccc; padding: 8px;")
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(6)
        
        self.total_links_label = QLabel("Ссылок найдено: 0")
        self.total_links_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.total_rows_label = QLabel("Строк распаршено: 0")
        self.total_rows_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        stats_layout.addWidget(self.total_links_label)
        stats_layout.addWidget(self.total_rows_label)
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)

        # Кнопки действий
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        self.open_csv_button = QPushButton('CSV')
        self.open_csv_button.clicked.connect(self.open_csv)
        self.open_folder_button = QPushButton('Папка')
        self.open_folder_button.clicked.connect(self.open_folder)
        
        actions_layout.addWidget(self.open_csv_button)
        actions_layout.addWidget(self.open_folder_button)
        left_layout.addLayout(actions_layout)

        left_layout.addStretch()
        left_panel.setLayout(left_layout)

        # === ПРАВАЯ ЧАСТЬ: ТАБЛИЦА РЕЗУЛЬТАТОВ ===
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок таблицы
        table_header = QLabel("РЕЗУЛЬТАТЫ ПАРСИНГА")
        table_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px; background-color: white; border-bottom: 1px solid #cccccc;")
        right_layout.addWidget(table_header)

        # Таблица результатов - занимает всё доступное место
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(FIELD_ORDER))
        self.results_table.setHorizontalHeaderLabels([EXPORT_HEADERS_RU[FIELD_ORDER[i]] for i in range(len(FIELD_ORDER))])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setMinimumHeight(500)  # Минимум 50% экрана
        
        # Устанавливаем начальные ширины колонок
        for i in range(len(FIELD_ORDER)):
            self.results_table.setColumnWidth(i, 150)
        
        right_layout.addWidget(self.results_table)
        right_panel.setLayout(right_layout)

        # Добавляем панели в главный layout
        main_hlayout.addWidget(left_panel)
        main_hlayout.addWidget(right_panel)
        main_hlayout.setStretch(1, 1)  # Правая часть растягивается

        central_widget.setLayout(main_hlayout)

        # Нижняя панель: логи и ссылки (скрываемая)
        bottom_panel = QWidget()
        bottom_panel.setMaximumHeight(250)
        bottom_panel.setStyleSheet("background-color: white; border-top: 1px solid #cccccc;")
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 10, 10, 10)

        # Список ссылок
        links_widget = QWidget()
        links_widget.setFixedWidth(400)
        links_layout = QVBoxLayout()
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_label = QLabel("<b>Найденные ссылки:</b>")
        self.links_list = QListWidget()
        self.links_list.itemDoubleClicked.connect(self.open_link)
        links_layout.addWidget(links_label)
        links_layout.addWidget(self.links_list)
        links_widget.setLayout(links_layout)

        # Разделитель
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(links_widget)

        # Лог выполнения
        log_widget = QWidget()
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_label = QLabel("<b>Лог выполнения:</b>")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(log_label)
        log_layout.addWidget(self.log_text)
        log_widget.setLayout(log_layout)
        splitter.addWidget(log_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        bottom_layout.addWidget(splitter)
        bottom_panel.setLayout(bottom_layout)

        # Главный вертикальный layout
        main_vlayout = QVBoxLayout()
        main_vlayout.setSpacing(0)
        main_vlayout.setContentsMargins(0, 0, 0, 0)
        main_vlayout.addWidget(central_widget)
        main_vlayout.addWidget(bottom_panel)

        # Контейнер для всего
        container = QWidget()
        container.setLayout(main_vlayout)
        self.setCentralWidget(container)

        # Скрываемая логика
        self.bottom_panel_visible = True
        self.toggle_logs_button = QPushButton('Скрыть логи и ссылки')
        self.toggle_logs_button.clicked.connect(self.toggle_logs_visibility)
        self.toggle_logs_button.setStyleSheet("padding: 6px; font-size: 12px;")
        
        # Добавляем кнопку в левую панель
        left_layout.addWidget(self.toggle_logs_button)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_label = QLabel("Готов к работе")
        self.statusBar.addPermanentWidget(self.status_label)
        self.statusBar.setStyleSheet("color: black;")

        # Меню
        self.create_menu()

    def create_menu(self):
        """Создание меню"""
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("Файл")
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        help_menu = menubar.addMenu("Помощь")
        about_action = help_menu.addAction("О программе")
        about_action.triggered.connect(self.show_about)

    def on_checkbox_toggled(self, checkbox_type):
        """Обработка переключения чекбоксов"""
        if checkbox_type == 'region' and self.region_checkbox.isChecked():
            self.rosunimed_checkbox.setChecked(False)
        elif checkbox_type == 'rosunimed' and self.rosunimed_checkbox.isChecked():
            self.region_checkbox.setChecked(False)

    def append_log(self, text):
        """Добавление записи в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {text}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def start_parsing(self):
        """Запуск полного цикла парсинга"""
        search_text = self.search_input.currentText().strip()
        if not search_text:
            QMessageBox.warning(self, "Внимание", "Введите поисковый запрос")
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.links_list.clear()
        self.log_text.clear()
        self.all_rows = []
        
        self.append_log("=== ЗАПУСК ПОЛНОГО ЦИКЛА ===")
        self.append_log(f"Поисковый запрос: {search_text}")
        
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        try:
            max_contracts = int(self.max_contracts_input.text())
            timeout_ms = int(self.timeout_ms_input.text())
            expand_rounds = int(self.expand_rounds_input.text())
            page_load_delay = int(self.page_load_delay_input.text())
            expand_delay = int(self.expand_delay_input.text())
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка", f"Неверный формат числового параметра: {e}")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            return

        self.thread = UnifiedParserWorker(
            search_text=search_text,
            date_from=date_from,
            date_to=date_to,
            moscow_only=self.region_checkbox.isChecked(),
            rosunimed_only=self.rosunimed_checkbox.isChecked(),
            max_contracts=max_contracts,
            archive_dir=self.archive_dir_input.text(),
            out_csv=self.csv_file_input.text(),
            out_xlsx=self.xlsx_file_input.text() if self.xlsx_file_input.text() else None,
            headed=False,
            trace=False,
            timeout_ms=timeout_ms,
            expand_rounds=expand_rounds,
            page_load_delay=page_load_delay,
            expand_delay=expand_delay
        )
        
        self.thread.update_progress.connect(self.progress_bar.setValue)
        self.thread.update_output.connect(self.append_log)
        self.thread.link_found.connect(self.on_link_found)
        self.thread.row_parsed.connect(self.add_row_to_table)
        self.thread.data_parsed.connect(self.on_data_parsed)
        self.thread.finished.connect(self.on_parsing_finished)
        
        self.thread.start()
        self.status_label.setText("Выполняется парсинг...")

    def stop_parsing(self):
        """Остановка парсинга"""
        if self.thread and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()
            self.append_log("Парсинг остановлен пользователем")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setText("Остановлено")

    def toggle_logs_visibility(self):
        """Скрыть/раскрыть панель логов и ссылок"""
        if self.bottom_panel_visible:
            # Скрыть
            self.bottom_panel.setVisible(False)
            self.toggle_logs_button.setText('▶ Раскрыть логи и ссылки')
            self.bottom_panel_visible = False
        else:
            # Раскрыть
            self.bottom_panel.setVisible(True)
            self.toggle_logs_button.setText('▼ Скрыть логи и ссылки')
            self.bottom_panel_visible = True

    def add_row_to_table(self, row_data: dict):
        """Добавление строки данных в таблицу результатов"""
        row_position = self.results_table.rowCount()
        self.results_table.insertRow(row_position)
        
        for col_idx, field_name in enumerate(FIELD_ORDER):
            value = row_data.get(field_name, "")
            item = QTableWidgetItem(str(value) if value else "")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Только для чтения
            self.results_table.setItem(row_position, col_idx, item)
        
        # Автопрокрутка к новой строке
        self.results_table.scrollToBottom()

    def on_link_found(self, link):
        """Обработка найденной ссылки"""
        self.links_list.addItem(link)
        count = self.links_list.count()
        self.total_links_label.setText(f"Ссылок найдено: {count}")

    def on_data_parsed(self, count):
        """Обработка добавленных строк данных"""
        current_total = len(self.all_rows)
        self.all_rows.extend([{}] * count)  # Просто для подсчета
        self.total_rows_label.setText(f"Строк распаршено: {len(self.all_rows)}")

    def on_parsing_finished(self, rows):
        """Завершение парсинга"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100)
        
        if rows:
            self.all_rows = rows
            self.total_rows_label.setText(f"Строк распаршено: {len(rows)}")
            self.append_log(f"=== ЗАВЕРШЕНО. Всего строк: {len(rows)} ===")
            self.status_label.setText(f"Готово. Строк: {len(rows)}")
            
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setText("Парсинг завершен успешно!")
            msg.setInformativeText(f"Найдено ссылок: {self.links_list.count()}\nРаспаршено строк: {len(rows)}")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        else:
            self.append_log("=== ЗАВЕРШЕНО БЕЗ ДАННЫХ ===")
            self.status_label.setText("Завершено без данных")

    def open_link(self, item):
        """Открытие ссылки в браузере"""
        url = item.text()
        QDesktopServices.openUrl(QUrl(url))

    def open_csv(self):
        """Открытие CSV файла"""
        csv_path = Path(self.csv_file_input.text())
        if not csv_path.exists():
            QMessageBox.warning(self, "Внимание", "CSV файл еще не создан")
            return
        try:
            import os
            os.startfile(csv_path.resolve())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть CSV: {e}")

    def open_folder(self):
        """Открытие папки с результатами"""
        archive_dir = Path(self.archive_dir_input.text())
        if not archive_dir.exists():
            QMessageBox.warning(self, "Внимание", "Папка архива еще не создана")
            return
        try:
            import os
            os.startfile(archive_dir.resolve())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть папку: {e}")

    def show_about(self):
        """О программе"""
        QMessageBox.about(
            self,
            "О программе",
            "Универсальный парсер ЕИС\n\n"
            "Объединяет поиск ссылок и парсинг данных\n"
            "в едином цикле с накоплением результатов."
        )


def launch_gui():
    """Запуск GUI приложения"""
    app = QApplication(sys.argv)
    window = UnifiedParserApp()
    window.show()
    sys.exit(app.exec_())


def main():
    """Точка входа"""
    parser = argparse.ArgumentParser(description="Unified EIS Parser (Link Finder + Parser)")
    parser.add_argument("--gui", action="store_true", help="Запуск в графическом интерфейсе")
    parser.add_argument("--search", type=str, help="Поисковый запрос")
    parser.add_argument("--date-from", type=str, help="Дата с (YYYY-MM-DD)")
    parser.add_argument("--date-to", type=str, help="Дата по (YYYY-MM-DD)")
    parser.add_argument("--max-contracts", type=int, default=20, help="Максимум контрактов")
    parser.add_argument("--moscow-only", action="store_true", help="Только Москва и МО")
    parser.add_argument("--rosunimed-only", action="store_true", help="Только Росунимед")
    parser.add_argument("--archive-dir", default="archive", help="Папка архива")
    parser.add_argument("--out-csv", default="export/unified_result.csv", help="Выходной CSV")
    parser.add_argument("--out-xlsx", default=None, help="Выходной XLSX")
    parser.add_argument("--headed", action="store_true", help="Браузер с окном")
    parser.add_argument("--timeout-ms", type=int, default=90000, help="Таймаут")
    parser.add_argument("--expand-rounds", type=int, default=5, help="Раунды раскрытия")
    
    args = parser.parse_args()
    
    if args.gui or not args.search:
        launch_gui()
    else:
        # Консольный режим
        worker = UnifiedParserWorker(
            search_text=args.search,
            date_from=args.date_from or (datetime.now().strftime("%Y-%m-%d")),
            date_to=args.date_to or (datetime.now().strftime("%Y-%m-%d")),
            moscow_only=args.moscow_only,
            rosunimed_only=args.rosunimed_only,
            max_contracts=args.max_contracts,
            archive_dir=args.archive_dir,
            out_csv=args.out_csv,
            out_xlsx=args.out_xlsx,
            headed=args.headed,
            trace=False,
            timeout_ms=args.timeout_ms,
            expand_rounds=args.expand_rounds,
            page_load_delay=1200,
            expand_delay=800
        )
        
        def print_output(text):
            print(text)
        
        def print_link(link):
            print(f"Найдена ссылка: {link}")
        
        def print_data(count):
            print(f"Добавлено строк: {count}")
        
        def on_finished(rows):
            print(f"\n=== ЗАВЕРШЕНО ===")
            print(f"Всего строк: {len(rows)}")
        
        worker.update_output.connect(print_output)
        worker.link_found.connect(print_link)
        worker.data_parsed.connect(print_data)
        worker.finished.connect(on_finished)
        
        worker.run()


if __name__ == "__main__":
    main()
