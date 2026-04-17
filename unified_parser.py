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
import urllib.parse

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
import glob
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
    QHeaderView, QFrame, QScrollArea, QTabWidget, QGroupBox, QDialogButtonBox
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

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# Настройка логирования
logging.basicConfig(
    filename='unified_parser_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


class DatabaseLoaderWorker(QThread):
    """Поток для загрузки базы данных МНН, формы выпуска и дозировки"""
    finished = pyqtSignal(list, int)  # reference_data, rows_loaded
    error = pyqtSignal(str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        try:
            if not OPENPYXL_AVAILABLE:
                self.error.emit("Библиотека openpyxl не установлена")
                return
            
            # Используем pandas как в ЛС-парсер-лайт.py для надежности
            import pandas as pd
            xl_file = pd.ExcelFile(self.file_path)
            
            # Ищем лист с именем, начинающимся с "esklp_smnn" как в ЛС-парсер-лайт.py
            smnn_sheet_name = None
            for sheet_name in xl_file.sheet_names:
                if sheet_name.startswith("esklp_smnn"):
                    smnn_sheet_name = sheet_name
                    break
            
            if not smnn_sheet_name:
                # Пробуем найти любой лист содержащий 'esklp'
                for sheet_name in xl_file.sheet_names:
                    if 'esklp' in sheet_name.lower():
                        smnn_sheet_name = sheet_name
                        break
            
            if not smnn_sheet_name:
                self.error.emit(f"Лист 'esklp_smnn' не найден. Доступные листы: {xl_file.sheet_names}")
                xl_file.close()
                return
            
            # Читаем данные без заголовков, чтобы получить полный контроль над обработкой строк
            # header=None означает, что все строки читаются как данные
            df = pd.read_excel(self.file_path, sheet_name=smnn_sheet_name, header=None)
            
            # Пропускаем первые 4 строки (индексы 0-3), так как они содержат артефакты:
            # Строка 0: Заголовки столбцов
            # Строка 1: nan | nan | Кол-во
            # Строка 2: nan | nan | nan
            # Строка 3: 1 | 4 | 5 (номера столбцов)
            # Реальные данные начинаются с индекса 4
            df = df.iloc[4:].reset_index(drop=True)
            
            # Формируем reference_data в том же формате
            reference_data = []
            rows_loaded = 0
            
            for idx, row in df.iterrows():
                mnn_val = row.iloc[0]  # Столбец 0: Стандартизованное МНН
                form_val = row.iloc[3]  # Столбец 3: Стандартизованная лекарственная форма
                dose_val = row.iloc[8]  # Столбец 9 (индекс 8): Дозировка
                
                mnn_str = str(mnn_val).strip() if pd.notna(mnn_val) else ""
                form_str = str(form_val).strip() if pd.notna(form_val) else ""
                dose_str = str(dose_val).strip() if pd.notna(dose_val) else ""
                
                # Пропускаем строки где МНН пустое или похоже на номер столбца
                if mnn_str and mnn_str not in ['1', '2', '3', '4', '5'] and not mnn_str.isdigit():
                    reference_data.append({
                        'mnn': mnn_str,
                        'release_form': form_str,
                        'dose': dose_str
                    })
                    rows_loaded += 1
            
            xl_file.close()
            self.finished.emit(reference_data, rows_loaded)
            
        except Exception as e:
            logging.error(f"Ошибка загрузки базы данных: {e}", exc_info=True)
            self.error.emit(str(e))


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
                 timeout_ms, expand_rounds, page_load_delay, expand_delay, results_table=None):
        super().__init__()
        self.search_text = search_text
        self.date_from = date_from
        self.date_to = date_to
        self.moscow_only = moscow_only
        self.rosunimed_only = rosunimed_only
        self.max_contracts = max_contracts  # Целевое количество контрактов в итоговой таблице
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
        self.processed_links_count = 0  # Количество обработанных ссылок
        self.results_table = results_table  # Ссылка на таблицу результатов для доступа к фильтру

    def run(self):
        try:
            # Алгоритм отбора ссылок:
            # 1. Первая партия = max_contracts * 3
            # 2. Если целевое количество контрактов не достигнуто - продолжаем отбор ссылок
            
            batch_size = self.max_contracts * 3  # Размер партии ссылок
            start_link_index = 0  # Индекс начала следующей партии
            total_unique_contracts = 0  # Количество уникальных контрактов в итоговой таблице
            
            self.update_output.emit(f"Целевое количество контрактов: {self.max_contracts}")
            self.update_output.emit(f"Размер партии ссылок: {batch_size}")
            
            all_parsed_links = set()  # Для отслеживания уже обработанных ссылок
            
            while total_unique_contracts < self.max_contracts:
                # Этап 1: Поиск ссылок (партиями)
                self.update_output.emit(f"=== Этап 1: Поиск ссылок (партия начиная с индекса {start_link_index}) ===")
                links, new_start_index, links_found_count = self.find_links_batch(start_link_index, batch_size)
                
                if not links:
                    self.update_output.emit("Больше ссылок не найдено!")
                    break
                
                # Фильтруем уже обработанные ссылки
                new_links = [link for link in links if link not in all_parsed_links]
                all_parsed_links.update(new_links)
                
                self.update_output.emit(f"Найдено новых ссылок для обработки: {len(new_links)} (всего отработано ссылок: {len(all_parsed_links)})")
                
                if not new_links:
                    self.update_output.emit("Все найденные ссылки уже обработаны, прекращаем поиск")
                    break
                
                # Этап 2: Парсинг каждой ссылки из партии
                self.update_output.emit("=== Этап 2: Парсинг данных ===")
                contracts_before = len(self.all_rows)
                self.parse_all_links(new_links)
                contracts_after = len(self.all_rows)
                
                # Считаем уникальные контракты только по видимым строкам таблицы (учитывая фильтр)
                if self.results_table is not None:
                    unique_contract_numbers = set()
                    for row in range(self.results_table.rowCount()):
                        if not self.results_table.isRowHidden(row):
                            item = self.results_table.item(row, FIELD_ORDER.index('reestr_number'))
                            if item and item.text():
                                unique_contract_numbers.add(item.text())
                    total_unique_contracts = len(unique_contract_numbers)
                else:
                    # Для консольного режима считаем по всем данным
                    unique_contract_numbers = set()
                    for row in self.all_rows:
                        if 'reestr_number' in row and row['reestr_number']:
                            unique_contract_numbers.add(row['reestr_number'])
                    total_unique_contracts = len(unique_contract_numbers)
                
                self.update_output.emit(f"Добавлено строк: {contracts_after - contracts_before}, всего строк: {len(self.all_rows)}")
                self.update_output.emit(f"Уникальных контрактов в итоговой таблице (с учётом фильтра): {total_unique_contracts}/{self.max_contracts}")
                
                if total_unique_contracts >= self.max_contracts:
                    self.update_output.emit("Целевое количество контрактов достигнуто!")
                    break
                
                if new_start_index is None or links_found_count < batch_size:
                    self.update_output.emit("Достигнут конец списка ссылок")
                    break
                
                start_link_index = new_start_index
            
            self.update_output.emit(f"=== ЗАВЕРШЕНО ===")
            self.update_output.emit(f"Всего отработано ссылок: {len(all_parsed_links)}")
            self.update_output.emit(f"Всего строк в итоговой таблице: {len(self.all_rows)}")
            self.update_output.emit(f"Уникальных контрактов: {total_unique_contracts}")
            
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
            "fz44": "on",
            "contractStageList": "1",
            "contractStageList_1": "on",
            "contractDateFrom": self.date_from,
            "contractDateTo": self.date_to,
            "sortBy": "UPDATE_DATE",
            "pageNumber": "1",
            "sortDirection": "false",
            "recordsPerPage": "_10",
            "strictEqual": "true"
        }

        # Фильтры: приоритет Росунимеду, затем Москва
        if self.rosunimed_only:
            # КРИТИЧЕСКИ ВАЖНО: customerIdOrg должен ТОЧНО совпадать с записью в базе ЕИС
            # Используем ПОЛНУЮ версию из ручной ссылки, а не минимальную
            # Формат: внутренний_ид:полное_название_организацииzZИННzZКППzZкод_причины_учётаzZОГРНzZдоп_поляzZещё_IDzZфинальный_ID
            # Значение взято из рабочей ручной ссылки (100% совпадение с ЕИС)
            full_customer_id = '14269:ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ ВЫСШЕГО ОБРАЗОВАНИЯ "РОССИЙСКИЙ УНИВЕРСИТЕТ МЕДИЦИНЫ" МИНИСТЕРСТВА ЗДРАВООХРАНЕНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИzZ03731000459zZ666998zZ63203zZ7707082145zZzZ770701001zZ1027739808898'
            params["customerIdOrg"] = full_customer_id
            
            logging.info(f"=== РОСУНИМЕД ФИЛЬТР ===")
            logging.info(f"customerIdOrg (raw): {params['customerIdOrg']}")
            
        elif self.moscow_only:
            params["customerPlace"] = "77000000000,50000000000"
            params["customerPlaceCodes"] = "77000000000,50000000000"

        # Кодируем параметры через urlencode для корректной передачи кириллицы
        # Важно: safe='' означает, что ВСЕ специальные символы будут закодированы, включая ':'
        # Это критично для customerIdOrg, где двоеточие должно стать %3A
        # Используем quote_via=urllib.parse.quote_plus для кодирования пробелей как '+' (как в ручной ссылке)
        url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote_plus)
        
        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ
        logging.info(f"=== ПОИСКОВЫЙ ЗАПРОС ===")
        logging.info(f"Поисковый текст: {self.search_text}")
        logging.info(f"Росунимед: {self.rosunimed_only}, Москва: {self.moscow_only}")
        logging.info(f"Даты: {self.date_from} - {self.date_to}")
        logging.info(f"Полный URL для поиска:")
        logging.info(f"{url}")
        logging.info(f"========================")
        
        # Вывод в интерфейс (сокращённая версия URL для читаемости)
        self.update_output.emit(f"Поиск: {self.search_text}")
        if self.rosunimed_only:
            self.update_output.emit("Фильтр: ТОЛЬКО РОСУНИМЕД")
        elif self.moscow_only:
            self.update_output.emit("Фильтр: ТОЛЬКО МОСКВА")
        self.update_output.emit(f"URL запроса (скопируйте для отладки):")
        self.update_output.emit(f"{url}")
        self.update_output.emit("")
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
            # Важно: используем safe='' и quote_plus для полного кодирования всех специальных символов
            url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote_plus)
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

                # Извлечение номера реестра из оригинальной ссылки
                reestr_match = re.search(r'reestrNumber=([0-9]+)', original_link)
                if reestr_match:
                    reestr_number = reestr_match.group(1)
                    
                    # Формируем оба URL: для common-info.html и payment-info-and-target-of-order.html
                    common_info_url = f"https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber={reestr_number}"
                    payment_url = f"https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html?reestrNumber={reestr_number}"
                    
                    # Сохраняем как кортеж (payment_url, common_info_url)
                    all_links.add((payment_url, common_info_url))
                    contracts_count += 1
                    self.link_found.emit(payment_url)
                    self.update_output.emit(f"Найдено контрактов: {contracts_count}/{self.max_contracts}")

        self.found_links = list(all_links)
        return self.found_links

    def find_links_batch(self, start_index, batch_size):
        """Поиск ссылок на контракты партиями
        
        Args:
            start_index: Индекс первой ссылки для отбора (0-based)
            batch_size: Количество ссылок для отбора
            
        Returns:
            tuple: (список кортежей ссылок, следующий индекс для продолжения, количество найденных ссылок)
        """
        base_url = "https://zakupki.gov.ru/epz/contract/search/results.html"
        params = {
            "searchString": self.search_text,
            "morphology": "on",
            "fz44": "on",
            "contractStageList": "1",
            "contractStageList_1": "on",
            "contractDateFrom": self.date_from,
            "contractDateTo": self.date_to,
            "sortBy": "UPDATE_DATE",
            "pageNumber": "1",
            "sortDirection": "false",
            "recordsPerPage": "_10",
            "strictEqual": "true"
        }

        # Фильтры: приоритет Росунимеду, затем Москва
        if self.rosunimed_only:
            full_customer_id = '14269:ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ ВЫСШЕГО ОБРАЗОВАНИЯ "РОССИЙСКИЙ УНИВЕРСИТЕТ МЕДИЦИНЫ" МИНИСТЕРСТВА ЗДРАВООХРАНЕНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИzZ03731000459zZ666998zZ63203zZ7707082145zZzZ770701001zZ1027739808898'
            params["customerIdOrg"] = full_customer_id
            
        elif self.moscow_only:
            params["customerPlace"] = "77000000000,50000000000"
            params["customerPlaceCodes"] = "77000000000,50000000000"

        url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote_plus)
        
        self.update_output.emit(f"Поиск: {self.search_text}")
        if self.rosunimed_only:
            self.update_output.emit("Фильтр: ТОЛЬКО РОСУНИМЕД")
        elif self.moscow_only:
            self.update_output.emit("Фильтр: ТОЛЬКО МОСКВА")
        self.update_output.emit("")
        self.update_progress.emit(5)

        # Инициализация WebDriver (если еще не создан)
        if not self.driver:
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

        all_links = []
        current_index = 0  # Текущий индекс ссылки (глобальный)
        links_found_count = 0  # Общее количество найденных ссылок в этой партии

        # Цикл по страницам результатов
        for page in range(1, total_pages + 1):
            params["pageNumber"] = str(page)
            url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote_plus)
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

            for original_link in unique_links:
                # Проверка на CAPTCHA
                if "captcha" in self.driver.page_source.lower():
                    self.update_output.emit("Обнаружена CAPTCHA!")
                    time.sleep(2)

                # Извлечение номера реестра из оригинальной ссылки
                reestr_match = re.search(r'reestrNumber=([0-9]+)', original_link)
                if reestr_match:
                    reestr_number = reestr_match.group(1)
                    
                    # Формируем оба URL
                    common_info_url = f"https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber={reestr_number}"
                    payment_url = f"https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html?reestrNumber={reestr_number}"
                    
                    # Проверяем, попадает ли ссылка в диапазон партии
                    if current_index >= start_index and len(all_links) < batch_size:
                        all_links.append((payment_url, common_info_url))
                        self.link_found.emit(payment_url)
                        links_found_count += 1
                        self.update_output.emit(f"Ссылка {len(all_links)}/{batch_size}: {payment_url}")
                    
                    current_index += 1
                    
                    # Если набрали нужное количество ссылок - выходим
                    if len(all_links) >= batch_size:
                        break
            
            # Если набрали нужное количество ссылок - выходим из цикла по страницам
            if len(all_links) >= batch_size:
                break

        # Определяем следующий индекс для продолжения
        next_start_index = current_index + 1 if current_index > 0 else None
        
        self.update_output.emit(f"Найдено ссылок в партии: {len(all_links)} (начиная с индекса {start_index})")
        
        return all_links, next_start_index, links_found_count

    def parse_all_links(self, links: List[tuple]):
        """Парсинг всех ссылок и накопление данных
        
        Args:
            links: Список кортежей (payment_url, common_info_url)
        """
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
                
                for idx, link_tuple in enumerate(links, start=1):
                    # Проверка: достигнут ли лимит контрактов перед обработкой следующей ссылки
                    if self.results_table is not None:
                        unique_contract_numbers = set()
                        for row in range(self.results_table.rowCount()):
                            if not self.results_table.isRowHidden(row):
                                item = self.results_table.item(row, FIELD_ORDER.index('reestr_number'))
                                if item and item.text():
                                    unique_contract_numbers.add(item.text())
                        if len(unique_contract_numbers) >= self.max_contracts:
                            self.update_output.emit(f"Достигнуто целевое количество контрактов ({self.max_contracts}), остановка парсинга")
                            break
                    
                    # Поддержка обоих форматов: кортеж (payment_url, common_info_url) или просто строка
                    if isinstance(link_tuple, tuple):
                        payment_url, common_info_url = link_tuple
                    else:
                        payment_url = link_tuple
                        # Генерируем common_info_url из payment_url
                        common_info_url = payment_url.replace("payment-info-and-target-of-order.html", "common-info.html")
                    
                    self.update_output.emit(f"[{idx}/{len(links)}] Обработка: {payment_url}")
                    progress = 30 + int((idx / len(links)) * 60)
                    self.update_progress.emit(progress)
                    
                    page = await context.new_page()
                    try:
                        rows = await parser.parse_url(page, payment_url, archive_dir=archive_dir, save_trace=self.trace, common_info_url=common_info_url)
                        self.all_rows.extend(rows)
                        # Отправляем каждую строку для отображения в таблице
                        for row in rows:
                            self.row_parsed.emit(row)
                        self.data_parsed.emit(len(rows))
                        self.update_output.emit(f"  -> добавлено строк: {len(rows)}, всего: {len(self.all_rows)}")
                    except Exception as exc:
                        self.update_output.emit(f"  -> ошибка: {exc}")
                        logging.error(f"Ошибка парсинга {payment_url}: {exc}")
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
        self.db_loader_thread = None  # Поток для загрузки базы данных
        self.all_rows = []
        self.filter_before_search = ""  # Фильтр МНН, установленный ДО поиска
        self.reference_data = []  # Список словарей {mnn, release_form, dose} из базы
        self.mnn_list = []  # Список уникальных МНН для автокомплита
        self.mnn_model = QStringListModel()  # Модель для автокомплита МНН
        self.forms_for_mnn = {}  # МНН -> список форм выпуска
        self.doses_for_mnn = {}  # МНН -> список дозировок

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle('Универсальный парсер ЕИС (Поиск + Парсинг)')
        self.setGeometry(100, 100, 1600, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный горизонтальный layout: слева панель управления, справа таблица
        main_hlayout = QHBoxLayout()
        main_hlayout.setSpacing(0)
        main_hlayout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            QMainWindow { background-color: #ffffff; }
            QLabel { font-size: 12px; color: #000000; }
            QLineEdit, QDateEdit, QComboBox { 
                font-size: 12px; padding: 4px; 
                border: 1px solid #999999; 
                background-color: white;
            }
            QLineEdit#search_input, QComboBox#search_input, QLineEdit#filter_result_input, QLineEdit#filter_form_input, QLineEdit#filter_dose_input, QComboBox#filter_result_input, QComboBox#filter_form_input, QComboBox#filter_dose_input {
                background-color: #FFFDE7;
                color: #000000;
            }
            QLineEdit#nmcc_input {
                background-color: #E3F2FD;
                color: #000000;
            }
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
                border: 1px solid #000000;
            }
            QPushButton { 
                font-size: 12px; padding: 6px 12px; 
                background-color: #ffffff; color: #000000; 
                border: 1px solid #000000; 
            }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:disabled { background-color: #f0f0f0; color: #999999; border: 1px solid #cccccc; }
            QCheckBox { font-size: 12px; color: #000000; spacing: 4px; }
            QProgressBar { 
                border: 1px solid #999999; 
                text-align: center; font-size: 10px;
                background-color: #ffffff;
            }
            QProgressBar::chunk { background-color: #000000; }
            QTextEdit { 
                font-size: 10px; border: 1px solid #999999; 
                background-color: white; font-family: 'Consolas', monospace;
            }
            QTabWidget::pane { 
                border: 1px solid #999999; 
                background-color: white; 
            }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab { 
                background-color: #e0e0e0; 
                color: #333333; 
                padding: 6px 12px; 
                margin-right: 2px;
                border: 1px solid #999999;
                border-bottom: none;
            }
            QTabBar::tab:selected { 
                background-color: #ffffff; 
                color: #000000;
                border-bottom: 1px solid #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected { background-color: #f5f5f5; }
            QTableWidget { 
                font-size: 11px; 
                border: 1px solid #999999; 
                background-color: white;
                gridline-color: #dddddd;
            }
            QTableWidget::item { padding: 4px 6px; }
            QTableWidget::item:hover { background-color: #f0f0f0; }
            QHeaderView::section { 
                background-color: #ffffff; 
                color: #000000; 
                padding: 6px; 
                border: 1px solid #999999;
                font-weight: bold;
                font-size: 11px;
            }
            QHeaderView::section:hover { background-color: #e0e0e0; }
            QScrollArea { border: none; background-color: transparent; }
            QSplitter::handle { background-color: #999999; width: 4px; }
            QStatusBar { 
                background-color: #ffffff; 
                color: #000000; 
                font-size: 11px;
                padding: 4px;
                border-top: 1px solid #999999;
            }
            QGroupBox { 
                font-weight: bold; 
                border: 1px solid #999999; 
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        # === ЛЕВАЯ ПАНЕЛЬ УПРАВЛЕНИЯ (300px) ===
        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(8, 8, 8, 8)

        # Вкладки для разделения настроек
        tab_widget = QTabWidget()
        
        # === ВКЛАДКА 1: ОСНОВНАЯ ===
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout()
        main_tab_layout.setSpacing(8)
        main_tab_layout.setContentsMargins(4, 8, 4, 4)

        # Поисковый запрос - используем QComboBox как в ЛС-парсер-лайт.py для автокомплита
        search_label = QLabel("Поисковый запрос (МНН):")
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText('Введите МНН')
        self.search_input.setInsertPolicy(QComboBox.NoInsert)
        main_tab_layout.addWidget(search_label)
        main_tab_layout.addWidget(self.search_input)

        # Даты
        date_layout = QHBoxLayout()
        date_layout.setSpacing(6)
        
        date_from_label = QLabel("С:")
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        
        date_to_label = QLabel("По:")
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        
        date_layout.addWidget(date_from_label)
        date_layout.addWidget(self.date_from)
        date_layout.addWidget(date_to_label)
        date_layout.addWidget(self.date_to)
        main_tab_layout.addLayout(date_layout)

        # Макс. контрактов
        max_contracts_label = QLabel("Макс. контрактов:")
        self.max_contracts_input = QLineEdit()
        self.max_contracts_input.setText("20")
        main_tab_layout.addWidget(max_contracts_label)
        main_tab_layout.addWidget(self.max_contracts_input)

        # Фильтры
        filter_group = QGroupBox("Фильтры")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(4)
        
        self.region_checkbox = QCheckBox('Только Москва и МО')
        self.rosunimed_checkbox = QCheckBox('Только Росунимед')
        self.region_checkbox.toggled.connect(lambda: self.on_checkbox_toggled('region'))
        self.rosunimed_checkbox.toggled.connect(lambda: self.on_checkbox_toggled('rosunimed'))
        
        filter_layout.addWidget(self.region_checkbox)
        filter_layout.addWidget(self.rosunimed_checkbox)
        filter_group.setLayout(filter_layout)
        main_tab_layout.addWidget(filter_group)

        # Фильтр по МНН (под фильтрами) - используем QComboBox для автокомплита
        filter_result_label = QLabel("Фильтр по МНН:")
        self.filter_result_input = QComboBox()
        self.filter_result_input.setEditable(True)
        self.filter_result_input.setObjectName("filter_result_input")
        self.filter_result_input.setPlaceholderText('Введите текст для фильтрации')
        self.filter_result_input.setInsertPolicy(QComboBox.NoInsert)
        main_tab_layout.addWidget(filter_result_label)
        main_tab_layout.addWidget(self.filter_result_input)

        # Фильтр по форме выпуска - используем QComboBox для автокомплита
        filter_form_label = QLabel("Фильтр по форме выпуска:")
        self.filter_form_input = QComboBox()
        self.filter_form_input.setEditable(True)
        self.filter_form_input.setObjectName("filter_form_input")
        self.filter_form_input.setPlaceholderText('Введите текст для фильтрации')
        self.filter_form_input.setInsertPolicy(QComboBox.NoInsert)
        main_tab_layout.addWidget(filter_form_label)
        main_tab_layout.addWidget(self.filter_form_input)

        # Фильтр по дозировке - используем QComboBox для автокомплита
        filter_dose_label = QLabel("Фильтр по дозировке:")
        self.filter_dose_input = QComboBox()
        self.filter_dose_input.setEditable(True)
        self.filter_dose_input.setObjectName("filter_dose_input")
        self.filter_dose_input.setPlaceholderText('Введите текст для фильтрации')
        self.filter_dose_input.setInsertPolicy(QComboBox.NoInsert)
        main_tab_layout.addWidget(filter_dose_label)
        main_tab_layout.addWidget(self.filter_dose_input)

        # Кнопка "Фильтровать" (под полями фильтров)
        self.filter_button = QPushButton('ФИЛЬТРОВАТЬ')
        self.filter_button.setMinimumHeight(30)
        self.filter_button.clicked.connect(self.apply_filter)
        main_tab_layout.addWidget(self.filter_button)

        # Кнопка загрузки базы данных с индикатором статуса
        db_button_layout = QHBoxLayout()
        self.load_db_button = QPushButton('База данных')
        self.load_db_button.setMinimumHeight(30)
        self.load_db_button.clicked.connect(self.load_reference_database)
        
        # Индикатор статуса базы данных (красный/зеленый кружок)
        self.db_status_indicator = QLabel()
        self.db_status_indicator.setFixedSize(12, 12)
        self.db_status_indicator.setStyleSheet("background-color: red; border-radius: 6px;")
        self.db_status_indicator.setToolTip("База данных не загружена")
        
        db_button_layout.addWidget(self.load_db_button)
        db_button_layout.addWidget(self.db_status_indicator)
        db_button_layout.addStretch()
        main_tab_layout.addLayout(db_button_layout)

        # Небольшой отступ перед кнопкой "Запустить"
        main_tab_layout.addSpacing(8)

        # Кнопка запуска (светло-салатовый цвет)
        self.start_button = QPushButton('ЗАПУСТИТЬ')
        self.start_button.setMinimumHeight(35)
        self.start_button.setStyleSheet("background-color: #C8E6C9;")
        self.start_button.clicked.connect(self.start_parsing)
        main_tab_layout.addWidget(self.start_button)

        # Кнопка стоп
        self.stop_button = QPushButton('СТОП')
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(35)
        self.stop_button.clicked.connect(self.stop_parsing)
        main_tab_layout.addWidget(self.stop_button)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(18)
        main_tab_layout.addWidget(self.progress_bar)

        main_tab_layout.addStretch()
        main_tab.setLayout(main_tab_layout)
        tab_widget.addTab(main_tab, "Основная")

        # === ВКЛАДКА 2: НАСТРОЙКИ ===
        settings_tab = QWidget()
        settings_tab_layout = QVBoxLayout()
        settings_tab_layout.setSpacing(8)
        settings_tab_layout.setContentsMargins(4, 8, 4, 4)

        # Таймауты и задержки
        timing_group = QGroupBox("Таймауты и задержки")
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
        
        timing_group.setLayout(timing_layout)
        settings_tab_layout.addWidget(timing_group)

        # Пути к файлам
        paths_group = QGroupBox("Пути к файлам")
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
        
        paths_group.setLayout(paths_layout)
        settings_tab_layout.addWidget(paths_group)

        settings_tab_layout.addStretch()
        settings_tab.setLayout(settings_tab_layout)
        tab_widget.addTab(settings_tab, "Настройки")

        left_layout.addWidget(tab_widget)

        # Статистика
        stats_group = QGroupBox("Статистика")
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(4)
        
        self.total_links_label = QLabel("Ссылок отработано: 0")
        self.filtered_count_label = QLabel("Отфильтровано позиций: 0")
        self.contracts_selected_label = QLabel("Контрактов отобрано: 0")
        
        stats_layout.addWidget(self.total_links_label)
        stats_layout.addWidget(self.filtered_count_label)
        stats_layout.addWidget(self.contracts_selected_label)
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)

        # Кнопка выгрузки в Excel (под блоком Статистика)
        self.export_excel_button = QPushButton('ВЫГРУЗИТЬ В EXCEL')
        self.export_excel_button.setMinimumHeight(35)
        self.export_excel_button.clicked.connect(self.export_to_excel)
        left_layout.addWidget(self.export_excel_button)

        # Кнопки действий
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        
        self.open_csv_button = QPushButton('Открыть CSV')
        self.open_csv_button.clicked.connect(self.open_csv)
        self.open_folder_button = QPushButton('Папка')
        self.open_folder_button.clicked.connect(self.open_folder)
        self.reset_button = QPushButton('СБРОС')
        self.reset_button.setStyleSheet("background-color: #ffcccc;")
        self.reset_button.clicked.connect(self.reset_data)
        
        actions_layout.addWidget(self.open_csv_button)
        actions_layout.addWidget(self.open_folder_button)
        actions_layout.addWidget(self.reset_button)
        left_layout.addLayout(actions_layout)

        left_layout.addStretch()
        left_panel.setLayout(left_layout)

        # === ПРАВАЯ ЧАСТЬ: ТАБЛИЦА РЕЗУЛЬТАТОВ ===
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Вкладки для таблиц: "Итоговая" и "НМЦК"
        self.tables_tab_widget = QTabWidget()
        
        # === ВКЛАДКА 1: ИТОГОВАЯ ТАБЛИЦА ===
        final_tab = QWidget()
        final_tab_layout = QVBoxLayout()
        final_tab_layout.setSpacing(0)
        final_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # Таблица результатов - занимает всё доступное место
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(FIELD_ORDER))
        self.results_table.setHorizontalHeaderLabels([EXPORT_HEADERS_RU[FIELD_ORDER[i]] for i in range(len(FIELD_ORDER))])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setMinimumHeight(450)
        # Подключаем сигнал для обработки кликов по ячейкам (для открытия ссылок и показа деталей)
        self.results_table.cellDoubleClicked.connect(self.on_results_table_double_click)
        
        # Устанавливаем начальные ширины колонок
        for i in range(len(FIELD_ORDER)):
            self.results_table.setColumnWidth(i, 150)
        
        final_tab_layout.addWidget(self.results_table)
        final_tab.setLayout(final_tab_layout)
        
        # === ВКЛАДКА 2: НМЦК ===
        self.nmcc_tab = QWidget()
        nmcc_tab_layout = QVBoxLayout()
        nmcc_tab_layout.setSpacing(8)
        nmcc_tab_layout.setContentsMargins(8, 8, 8, 8)
        
        # Верхняя панель с двумя колонками: ввод данных и итоговые данные
        top_panel = QHBoxLayout()
        top_panel.setSpacing(8)
        
        # === ЛЕВАЯ КОЛОНКА: Панель ввода данных для НМЦК ===
        input_group = QGroupBox("Ввод данных для расчета НМЦК")
        input_layout = QGridLayout()
        input_layout.setSpacing(6)
        
        # Поле 1: Цена за ед. измерения по 1 КП
        input_layout.addWidget(QLabel("Цена за ед. изм. по 1 КП (₽):"), 0, 0)
        self.nmcc_price1_input = QLineEdit()
        self.nmcc_price1_input.setPlaceholderText("0.00")
        self.nmcc_price1_input.setObjectName("nmcc_input")
        self.nmcc_price1_input.textChanged.connect(self.update_nmcc_summary)
        input_layout.addWidget(self.nmcc_price1_input, 0, 1)
        
        # Поле 2: Цена за ед. измерения по 2 КП
        input_layout.addWidget(QLabel("Цена за ед. изм. по 2 КП (₽):"), 1, 0)
        self.nmcc_price2_input = QLineEdit()
        self.nmcc_price2_input.setPlaceholderText("0.00")
        self.nmcc_price2_input.setObjectName("nmcc_input")
        self.nmcc_price2_input.textChanged.connect(self.update_nmcc_summary)
        input_layout.addWidget(self.nmcc_price2_input, 1, 1)
        
        # Поле 3: Цена за ед. измерения по 3 КП
        input_layout.addWidget(QLabel("Цена за ед. изм. по 3 КП (₽):"), 2, 0)
        self.nmcc_price3_input = QLineEdit()
        self.nmcc_price3_input.setPlaceholderText("0.00")
        self.nmcc_price3_input.setObjectName("nmcc_input")
        self.nmcc_price3_input.textChanged.connect(self.update_nmcc_summary)
        input_layout.addWidget(self.nmcc_price3_input, 2, 1)
        
        # Поле 4: Объем в ед. измерения
        input_layout.addWidget(QLabel("Объем в ед. измерения:"), 3, 0)
        self.nmcc_volume_input = QLineEdit()
        self.nmcc_volume_input.setPlaceholderText("0")
        self.nmcc_volume_input.setObjectName("nmcc_input")
        self.nmcc_volume_input.textChanged.connect(self.update_nmcc_summary)
        input_layout.addWidget(self.nmcc_volume_input, 3, 1)
        
        input_group.setLayout(input_layout)
        
        # === ПРАВАЯ КОЛОНКА: Итоговые данные ===
        summary_group = QGroupBox("Итоговые данные")
        summary_layout = QGridLayout()
        summary_layout.setSpacing(6)
        
        # Метки для отображения итоговых данных
        summary_layout.addWidget(QLabel("Средняя цена по КП (₽):"), 0, 0)
        self.nmcc_avg_kp_label = QLabel("0.00")
        self.nmcc_avg_kp_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        summary_layout.addWidget(self.nmcc_avg_kp_label, 0, 1)
        
        summary_layout.addWidget(QLabel("Средняя по ЕИС (₽):"), 1, 0)
        self.nmcc_avg_eis_label = QLabel("0.00")
        self.nmcc_avg_eis_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        summary_layout.addWidget(self.nmcc_avg_eis_label, 1, 1)
        
        summary_layout.addWidget(QLabel("Дельта средних цен (₽ / %):"), 2, 0)
        self.nmcc_price_delta_label = QLabel("0.00 (0.00%)")
        self.nmcc_price_delta_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        summary_layout.addWidget(self.nmcc_price_delta_label, 2, 1)
        
        summary_layout.addWidget(QLabel("Макс. отклонение по объему (ед. / %):"), 3, 0)
        self.nmcc_max_deviation_label = QLabel("0.00 (0.00%)")
        self.nmcc_max_deviation_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        summary_layout.addWidget(self.nmcc_max_deviation_label, 3, 1)
        
        summary_group.setLayout(summary_layout)
        
        # Добавляем обе колонки в верхнюю панель
        top_panel.addWidget(input_group, 1)
        top_panel.addWidget(summary_group, 1)
        
        nmcc_tab_layout.addLayout(top_panel)
        
        # Кнопки расчета НМЦК
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.nmcc_volume_btn = QPushButton("НМЦК по объему")
        self.nmcc_volume_btn.setToolTip("Найти 3 позиции с количеством, наиболее близким к указанному объему")
        buttons_layout.addWidget(self.nmcc_volume_btn)
        
        self.nmcc_avg_btn = QPushButton("НМЦК приближенный к КП")
        self.nmcc_avg_btn.setToolTip("Найти 3 позиции со средней ценой, наиболее близкой к средней по введенным КП")
        buttons_layout.addWidget(self.nmcc_avg_btn)
        
        self.nmcc_optimal_btn = QPushButton("НМЦК Оптимальный")
        self.nmcc_optimal_btn.setToolTip(
            "Оптимальный алгоритм:\n"
            "1. В приоритете 'вписаться в цену' (средняя цена ЕИС >= средней цены КП)\n"
            "2. Минимизировать разброс по объему (не более 50% отклонения)\n"
            "3. Баланс между ценой и объемом для наилучшего соответствия"
        )
        buttons_layout.addWidget(self.nmcc_optimal_btn)
        
        buttons_layout.addStretch()
        nmcc_tab_layout.addLayout(buttons_layout)
        
        # Таблица НМЦК
        nmcc_table_group = QGroupBox("Результат расчета НМЦК (3 позиции)")
        nmcc_table_layout = QVBoxLayout()
        nmcc_table_layout.setSpacing(0)
        nmcc_table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.nmcc_table = QTableWidget()
        self.nmcc_table.setColumnCount(len(FIELD_ORDER))
        self.nmcc_table.setHorizontalHeaderLabels([EXPORT_HEADERS_RU[FIELD_ORDER[i]] for i in range(len(FIELD_ORDER))])
        self.nmcc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.nmcc_table.horizontalHeader().setStretchLastSection(True)
        self.nmcc_table.verticalHeader().setVisible(False)
        self.nmcc_table.setAlternatingRowColors(True)
        self.nmcc_table.setMinimumHeight(300)
        self.nmcc_table.cellDoubleClicked.connect(self.open_nmcc_table_link)
        
        # Устанавливаем начальные ширины колонок
        for i in range(len(FIELD_ORDER)):
            self.nmcc_table.setColumnWidth(i, 150)
        
        nmcc_table_layout.addWidget(self.nmcc_table)
        nmcc_table_group.setLayout(nmcc_table_layout)
        nmcc_tab_layout.addWidget(nmcc_table_group)
        
        self.nmcc_tab.setLayout(nmcc_tab_layout)
        
        # Добавляем вкладки в виджет
        self.tables_tab_widget.addTab(final_tab, "Итоговая")
        self.tables_tab_widget.addTab(self.nmcc_tab, "НМЦК")
        
        # === ВКЛАДКА 3: НМЦК ручной подбор ===
        self.manual_nmcc_tab = QWidget()
        manual_nmcc_tab_layout = QVBoxLayout()
        manual_nmcc_tab_layout.setSpacing(8)
        manual_nmcc_tab_layout.setContentsMargins(8, 8, 8, 8)
        
        # Верхняя панель с двумя колонками: ввод данных и итоговые данные (аналогично вкладке НМЦК)
        manual_top_panel = QHBoxLayout()
        manual_top_panel.setSpacing(8)
        
        # === ЛЕВАЯ КОЛОНКА: Панель ввода данных для НМЦК ===
        manual_input_group = QGroupBox("Ввод данных для расчета НМЦК")
        manual_input_layout = QGridLayout()
        manual_input_layout.setSpacing(6)
        
        # Поле 1: Цена за ед. измерения по 1 КП
        manual_input_layout.addWidget(QLabel("Цена за ед. изм. по 1 КП (₽):"), 0, 0)
        self.manual_nmcc_price1_input = QLineEdit()
        self.manual_nmcc_price1_input.setPlaceholderText("0.00")
        self.manual_nmcc_price1_input.setObjectName("nmcc_input")
        self.manual_nmcc_price1_input.textChanged.connect(self.update_manual_nmcc_summary)
        manual_input_layout.addWidget(self.manual_nmcc_price1_input, 0, 1)
        
        # Поле 2: Цена за ед. измерения по 2 КП
        manual_input_layout.addWidget(QLabel("Цена за ед. изм. по 2 КП (₽):"), 1, 0)
        self.manual_nmcc_price2_input = QLineEdit()
        self.manual_nmcc_price2_input.setPlaceholderText("0.00")
        self.manual_nmcc_price2_input.setObjectName("nmcc_input")
        self.manual_nmcc_price2_input.textChanged.connect(self.update_manual_nmcc_summary)
        manual_input_layout.addWidget(self.manual_nmcc_price2_input, 1, 1)
        
        # Поле 3: Цена за ед. измерения по 3 КП
        manual_input_layout.addWidget(QLabel("Цена за ед. изм. по 3 КП (₽):"), 2, 0)
        self.manual_nmcc_price3_input = QLineEdit()
        self.manual_nmcc_price3_input.setPlaceholderText("0.00")
        self.manual_nmcc_price3_input.setObjectName("nmcc_input")
        self.manual_nmcc_price3_input.textChanged.connect(self.update_manual_nmcc_summary)
        manual_input_layout.addWidget(self.manual_nmcc_price3_input, 2, 1)
        
        # Поле 4: Объем в ед. измерения
        manual_input_layout.addWidget(QLabel("Объем в ед. измерения:"), 3, 0)
        self.manual_nmcc_volume_input = QLineEdit()
        self.manual_nmcc_volume_input.setPlaceholderText("0")
        self.manual_nmcc_volume_input.setObjectName("nmcc_input")
        self.manual_nmcc_volume_input.textChanged.connect(self.update_manual_nmcc_summary)
        manual_input_layout.addWidget(self.manual_nmcc_volume_input, 3, 1)
        
        manual_input_group.setLayout(manual_input_layout)
        
        # === ПРАВАЯ КОЛОНКА: Итоговые данные ===
        manual_summary_group = QGroupBox("Итоговые данные")
        manual_summary_layout = QGridLayout()
        manual_summary_layout.setSpacing(6)
        
        # Метки для отображения итоговых данных
        manual_summary_layout.addWidget(QLabel("Средняя цена по КП (₽):"), 0, 0)
        self.manual_nmcc_avg_kp_label = QLabel("0.00")
        self.manual_nmcc_avg_kp_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        manual_summary_layout.addWidget(self.manual_nmcc_avg_kp_label, 0, 1)
        
        manual_summary_layout.addWidget(QLabel("Средняя по ЕИС (₽):"), 1, 0)
        self.manual_nmcc_avg_eis_label = QLabel("0.00")
        self.manual_nmcc_avg_eis_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        manual_summary_layout.addWidget(self.manual_nmcc_avg_eis_label, 1, 1)
        
        manual_summary_layout.addWidget(QLabel("Дельта средних цен (₽ / %):"), 2, 0)
        self.manual_nmcc_price_delta_label = QLabel("0.00 (0.00%)")
        self.manual_nmcc_price_delta_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        manual_summary_layout.addWidget(self.manual_nmcc_price_delta_label, 2, 1)
        
        manual_summary_layout.addWidget(QLabel("Макс. отклонение по объему (ед. / %):"), 3, 0)
        self.manual_nmcc_max_deviation_label = QLabel("0.00 (0.00%)")
        self.manual_nmcc_max_deviation_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        manual_summary_layout.addWidget(self.manual_nmcc_max_deviation_label, 3, 1)
        
        manual_summary_group.setLayout(manual_summary_layout)
        
        # Добавляем обе колонки в верхнюю панель
        manual_top_panel.addWidget(manual_input_group, 1)
        manual_top_panel.addWidget(manual_summary_group, 1)
        
        manual_nmcc_tab_layout.addLayout(manual_top_panel)
        
        # Таблица для ручного подбора НМЦК
        manual_nmcc_table_group = QGroupBox("Позиции для НМЦК (ручной подбор)")
        manual_nmcc_table_layout = QVBoxLayout()
        manual_nmcc_table_layout.setSpacing(0)
        manual_nmcc_table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.manual_nmcc_table = QTableWidget()
        self.manual_nmcc_table.setColumnCount(len(FIELD_ORDER))
        self.manual_nmcc_table.setHorizontalHeaderLabels([EXPORT_HEADERS_RU[FIELD_ORDER[i]] for i in range(len(FIELD_ORDER))])
        self.manual_nmcc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.manual_nmcc_table.horizontalHeader().setStretchLastSection(True)
        self.manual_nmcc_table.verticalHeader().setVisible(False)
        self.manual_nmcc_table.setAlternatingRowColors(True)
        self.manual_nmcc_table.setMinimumHeight(300)
        self.manual_nmcc_table.cellDoubleClicked.connect(self.open_manual_nmcc_table_link)
        
        # Устанавливаем начальные ширины колонок
        for i in range(len(FIELD_ORDER)):
            self.manual_nmcc_table.setColumnWidth(i, 150)
        
        manual_nmcc_table_layout.addWidget(self.manual_nmcc_table)
        manual_nmcc_table_group.setLayout(manual_nmcc_table_layout)
        manual_nmcc_tab_layout.addWidget(manual_nmcc_table_group)
        
        self.manual_nmcc_tab.setLayout(manual_nmcc_tab_layout)
        self.tables_tab_widget.addTab(self.manual_nmcc_tab, "НМЦК ручной подбор")
        
        # Подключаем сигналы для синхронизации полей ввода НМЦК между вкладками
        self.nmcc_price1_input.textChanged.connect(self.sync_nmcc_price1)
        self.nmcc_price2_input.textChanged.connect(self.sync_nmcc_price2)
        self.nmcc_price3_input.textChanged.connect(self.sync_nmcc_price3)
        self.nmcc_volume_input.textChanged.connect(self.sync_nmcc_volume)
        
        self.manual_nmcc_price1_input.textChanged.connect(self.sync_manual_nmcc_price1)
        self.manual_nmcc_price2_input.textChanged.connect(self.sync_manual_nmcc_price2)
        self.manual_nmcc_price3_input.textChanged.connect(self.sync_manual_nmcc_price3)
        self.manual_nmcc_volume_input.textChanged.connect(self.sync_manual_nmcc_volume)
        
        # Флаг для предотвращения рекурсивной синхронизации
        self._syncing_nmcc_fields = False
        
        # Подключаем кнопки расчета
        self.nmcc_volume_btn.clicked.connect(self.calculate_nmcc_by_volume)
        self.nmcc_avg_btn.clicked.connect(self.calculate_nmcc_by_avg_price)
        self.nmcc_optimal_btn.clicked.connect(self.calculate_nmcc_optimal)
        
        right_layout.addWidget(self.tables_tab_widget)
        right_panel.setLayout(right_layout)

        # Добавляем панели в главный layout
        main_hlayout.addWidget(left_panel)
        main_hlayout.addWidget(right_panel)
        main_hlayout.setStretch(1, 1)

        central_widget.setLayout(main_hlayout)

        # Нижняя панель: логи и ссылки
        bottom_panel = QWidget()
        bottom_panel.setMaximumHeight(200)
        bottom_panel.setStyleSheet("background-color: white; border-top: 1px solid #999999;")
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(8, 8, 8, 8)

        # Список ссылок
        links_widget = QWidget()
        links_widget.setFixedWidth(350)
        links_layout = QVBoxLayout()
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_label = QLabel("Найденные ссылки:")
        links_label.setStyleSheet("font-weight: bold;")
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
        log_label = QLabel("Лог выполнения:")
        log_label.setStyleSheet("font-weight: bold;")
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
        
        help_action = help_menu.addAction("Инструкция")
        help_action.triggered.connect(self.show_help)

    def on_checkbox_toggled(self, checkbox_type):
        """Обработка переключения чекбоксов"""
        if checkbox_type == 'region' and self.region_checkbox.isChecked():
            self.rosunimed_checkbox.setChecked(False)
        elif checkbox_type == 'rosunimed' and self.rosunimed_checkbox.isChecked():
            self.region_checkbox.setChecked(False)

    def apply_filter(self):
        """Фильтрация таблицы по тексту в колонке МНН, форма выпуска и дозировка по кнопке"""
        filter_mnn = self.filter_result_input.currentText().strip().lower()
        filter_form = self.filter_form_input.currentText().strip().lower()
        filter_dose = self.filter_dose_input.currentText().strip().lower()
        
        # Находим индексы колонок
        mnn_column_index = -1
        form_column_index = -1
        dose_column_index = -1
        for i, field_name in enumerate(FIELD_ORDER):
            if field_name == 'mnn':
                mnn_column_index = i
            elif field_name == 'release_form':
                form_column_index = i
            elif field_name == 'dose':
                dose_column_index = i
        
        if mnn_column_index == -1 or form_column_index == -1 or dose_column_index == -1:
            return
        
        # Проходим по всем строкам и скрываем/показываем
        for row in range(self.results_table.rowCount()):
            mnn_item = self.results_table.item(row, mnn_column_index)
            form_item = self.results_table.item(row, form_column_index)
            dose_item = self.results_table.item(row, dose_column_index)
            
            mnn_text = mnn_item.text().lower() if mnn_item else ""
            form_text = form_item.text().lower() if form_item else ""
            dose_text = dose_item.text().lower() if dose_item else ""
            
            # Проверяем все три фильтра (если фильтр пустой - игнорируем)
            mnn_match = not filter_mnn or filter_mnn in mnn_text
            form_match = not filter_form or filter_form in form_text
            dose_match = not filter_dose or filter_dose in dose_text
            
            if mnn_match and form_match and dose_match:
                self.results_table.setRowHidden(row, False)
            else:
                self.results_table.setRowHidden(row, True)
        
        # Обновляем filter_before_search для последующего добавления строк
        self.filter_before_search = {
            'mnn': self.filter_result_input.currentText().strip(),
            'form': self.filter_form_input.currentText().strip(),
            'dose': self.filter_dose_input.currentText().strip()
        }

    def filter_table(self, filter_text):
        """Фильтрация таблицы по тексту в колонке МНН (ГРЛС) - устаревший метод"""
        filter_text = filter_text.strip().lower()
        
        # Находим индекс колонки МНН (ГРЛС) - в FIELD_ORDER это 'mnn'
        mnn_column_index = -1
        for i, field_name in enumerate(FIELD_ORDER):
            if field_name == 'mnn':
                mnn_column_index = i
                break
        
        if mnn_column_index == -1:
            return
        
        # Проходим по всем строкам и скрываем/показываем
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, mnn_column_index)
            cell_text = item.text().lower() if item else ""
            
            if not filter_text or filter_text in cell_text:
                self.results_table.setRowHidden(row, False)
            else:
                self.results_table.setRowHidden(row, True)

    def reset_data(self):
        """Сброс всех данных из таблицы с подтверждением"""
        reply = QMessageBox.question(
            self,
            "Подтверждение сброса",
            "Вы уверены, что хотите сбросить полученные данные?\n\nВсе данные из таблицы будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Очищаем таблицу
            self.results_table.setRowCount(0)
            # Очищаем таблицу НМЦК
            self.nmcc_table.setRowCount(0)
            # Очищаем таблицу НМЦК ручной подбор
            self.manual_nmcc_table.setRowCount(0)
            # Очищаем список ссылок
            self.links_list.clear()
            # Очищаем лог
            self.log_text.clear()
            # Сбрасываем счетчики
            self.total_links_label.setText("Ссылок отработано: 0")
            self.filtered_count_label.setText("Отфильтровано позиций: 0")
            self.contracts_selected_label.setText("Контрактов отобрано: 0")
            # Очищаем прогресс бар
            self.progress_bar.setValue(0)
            # Очищаем внутренний список данных
            self.all_rows = []
            # Сбрасываем фильтр
            self.filter_before_search = ""
            
            # Очищаем поля ввода НМЦК (синхронизируется между вкладками)
            self.nmcc_price1_input.clear()
            self.nmcc_price2_input.clear()
            self.nmcc_price3_input.clear()
            self.nmcc_volume_input.clear()
            
            # Сбрасываем итоговые данные
            self.nmcc_avg_kp_label.setText("0.00")
            self.nmcc_avg_eis_label.setText("0.00")
            self.nmcc_price_delta_label.setText("0.00 (0.00%)")
            self.nmcc_max_deviation_label.setText("0.00 (0.00%)")
            
            # Сбрасываем индикацию кнопок НМЦК
            self.nmcc_volume_btn.setStyleSheet("")
            self.nmcc_avg_btn.setStyleSheet("")
            self.nmcc_optimal_btn.setStyleSheet("")
            
            # Сбрасываем поля "Поисковый запрос" и фильтры
            self.search_input.setCurrentText("")
            self.filter_result_input.setCurrentText("")
            self.filter_form_input.setCurrentText("")
            self.filter_dose_input.setCurrentText("")
            
            # НЕ очищаем базу данных (reference_data остается загруженной)
            # Обновляем статус
            self.status_label.setText("Данные сброшены")
            self.append_log("=== ДАННЫЕ СБРОШЕНЫ ПОЛЬЗОВАТЕЛЕМ ===")

    def export_to_excel(self):
        """Выгрузка видимых данных таблицы в Excel"""
        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, "Внимание", "Нет данных для выгрузки")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить в Excel",
            "",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Результаты"
            
            # Заголовки
            headers = [self.results_table.horizontalHeaderItem(i).text() 
                      for i in range(self.results_table.columnCount())]
            ws.append(headers)
            
            # Данные (только видимые строки)
            for row in range(self.results_table.rowCount()):
                if self.results_table.isRowHidden(row):
                    continue
                row_data = []
                for col in range(self.results_table.columnCount()):
                    item = self.results_table.item(row, col)
                    row_data.append(item.text() if item else "")
                ws.append(row_data)
            
            wb.save(file_path)
            QMessageBox.information(self, "Успех", f"Данные сохранены в {file_path}")
            self.append_log(f"Экспорт в Excel: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {e}")
            self.append_log(f"Ошибка экспорта в Excel: {e}")

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

        # Сохраняем значение фильтров ДО поиска
        self.filter_before_search = {
            'mnn': self.filter_result_input.currentText().strip(),
            'form': self.filter_form_input.currentText().strip(),
            'dose': self.filter_dose_input.currentText().strip()
        }

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.links_list.clear()
        self.log_text.clear()
        self.all_rows = []
        
        self.append_log("=== ЗАПУСК ПОЛНОГО ЦИКЛА ===")
        self.append_log(f"Поисковый запрос: {search_text}")
        if self.filter_before_search['mnn']:
            self.append_log(f"Фильтр МНН (до поиска): {self.filter_before_search['mnn']}")
        if self.filter_before_search['form']:
            self.append_log(f"Фильтр формы выпуска (до поиска): {self.filter_before_search['form']}")
        if self.filter_before_search['dose']:
            self.append_log(f"Фильтр дозировки (до поиска): {self.filter_before_search['dose']}")
        
        date_from = self.date_from.date().toString("dd.MM.yyyy")
        date_to = self.date_to.date().toString("dd.MM.yyyy")
        
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
            expand_delay=expand_delay,
            results_table=self.results_table
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
        # Если был установлен фильтр (до поиска или после), проверяем соответствие
        if self.filter_before_search:
            # filter_before_search может быть строкой (старый формат) или словарем (новый формат)
            if isinstance(self.filter_before_search, str):
                # Старый формат - только МНН
                mnn_value = row_data.get('mnn', '').lower()
                if self.filter_before_search.lower() not in mnn_value:
                    return
            elif isinstance(self.filter_before_search, dict):
                # Новый формат - словарь с фильтрами по МНН, форме и дозировке
                mnn_value = row_data.get('mnn', '').lower()
                form_value = row_data.get('release_form', '').lower()
                dose_value = row_data.get('dose', '').lower()
                
                filter_mnn = self.filter_before_search.get('mnn', '').lower()
                filter_form = self.filter_before_search.get('form', '').lower()
                filter_dose = self.filter_before_search.get('dose', '').lower()
                
                # Проверяем все три фильтра (если фильтр пустой - игнорируем)
                mnn_match = not filter_mnn or filter_mnn in mnn_value
                form_match = not filter_form or filter_form in form_value
                dose_match = not filter_dose or filter_dose in dose_value
                
                if not (mnn_match and form_match and dose_match):
                    return
        
        row_position = self.results_table.rowCount()
        self.results_table.insertRow(row_position)
        
        for col_idx, field_name in enumerate(FIELD_ORDER):
            value = row_data.get(field_name, "")
            
            # Для колонки contract_link создаем кликабельную ссылку
            if field_name == 'contract_link' and value:
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Только для чтения
                # Делаем текст синим и подчеркнутым как hyperlink
                font = item.font()
                font.setUnderline(True)
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.blue)
                # Сохраняем URL в data role для открытия
                item.setData(Qt.UserRole, value)
            else:
                item = QTableWidgetItem(str(value) if value else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Только для чтения
            
            self.results_table.setItem(row_position, col_idx, item)
        
        # Автопрокрутка к новой строке
        self.results_table.scrollToBottom()

    def on_link_found(self, link):
        """Обработка найденной ссылки"""
        self.links_list.addItem(link)
        count = self.links_list.count()
        self.total_links_label.setText(f"Ссылок отработано: {count}")

    def on_data_parsed(self, count):
        """Обработка добавленных строк данных"""
        current_total = len(self.all_rows)
        self.all_rows.extend([{}] * count)  # Просто для подсчета
        # Обновляем счетчик отфильтрованных позиций
        self.update_filtered_count()
        # Обновляем счетчик контрактов
        self.update_contracts_selected_count()

    def update_filtered_count(self):
        """Обновление счетчика отфильтрованных позиций"""
        visible_rows = 0
        for row in range(self.results_table.rowCount()):
            if not self.results_table.isRowHidden(row):
                visible_rows += 1
        self.filtered_count_label.setText(f"Отфильтровано позиций: {visible_rows}")

    def update_contracts_selected_count(self):
        """Обновление счетчика контрактов отобрано (уникальные номера реестров)"""
        unique_contract_numbers = set()
        for row in range(self.results_table.rowCount()):
            if not self.results_table.isRowHidden(row):
                item = self.results_table.item(row, FIELD_ORDER.index('reestr_number'))
                if item and item.text():
                    unique_contract_numbers.add(item.text())
        self.contracts_selected_label.setText(f"Контрактов отобрано: {len(unique_contract_numbers)}")

    def on_parsing_finished(self, rows):
        """Завершение парсинга"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100)
        
        if rows:
            self.all_rows = rows
            self.update_filtered_count()
            self.update_contracts_selected_count()
            self.append_log(f"=== ЗАВЕРШЕНО. Всего строк: {len(rows)} ===")
            self.status_label.setText(f"Готово. Строк: {len(rows)}")
            
            # Получаем количество уникальных контрактов
            unique_contract_numbers = set()
            for row in rows:
                if 'reestr_number' in row and row['reestr_number']:
                    unique_contract_numbers.add(row['reestr_number'])
            
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setText("Парсинг завершен успешно!")
            msg.setInformativeText(f"Ссылок отработано: {self.links_list.count()}\nКонтрактов отобрано: {len(unique_contract_numbers)}\nРаспаршено строк: {len(rows)}")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        else:
            self.append_log("=== ЗАВЕРШЕНО БЕЗ ДАННЫХ ===")
            self.status_label.setText("Завершено без данных")


    def open_link(self, item):
        """Открытие ссылки в браузере из списка links_list"""
        url = item.text()
        QDesktopServices.openUrl(QUrl(url))
    
    def on_results_table_double_click(self, row, column):
        """Обработка двойного клика по строке итоговой таблицы:
        - Если клик на колонку contract_link - открываем ссылку
        - Иначе - показываем модальное окно с деталями строки
        """
        # Проверяем, что кликнули на колонку contract_link
        contract_link_col = FIELD_ORDER.index('contract_link')
        if column == contract_link_col:
            self.open_table_link(row, column)
        else:
            # Собираем данные из строки и показываем диалог
            row_data_dict = {}
            for col_idx, field_name in enumerate(FIELD_ORDER):
                item = self.results_table.item(row, col_idx)
                if item:
                    row_data_dict[field_name] = item.text()
            
            self.show_row_details_dialog(row_data_dict)
    
    def open_table_link(self, row, column):
        """Открытие ссылки из таблицы при двойном клике на ячейку contract_link"""
        # Проверяем, что кликнули на колонку contract_link
        contract_link_col = FIELD_ORDER.index('contract_link')
        if column != contract_link_col:
            return
        
        item = self.results_table.item(row, column)
        if item:
            url = item.data(Qt.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))
    
    def open_nmcc_table_link(self, row, column):
        """Открытие ссылки из таблицы НМЦК при двойном клике на ячейку contract_link"""
        # Проверяем, что кликнули на колонку contract_link
        contract_link_col = FIELD_ORDER.index('contract_link')
        if column != contract_link_col:
            return
        
        item = self.nmcc_table.item(row, column)
        if item:
            url = item.data(Qt.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))
    
    def open_manual_nmcc_table_link(self, row, column):
        """Открытие ссылки из таблицы НМЦК ручной подбор при двойном клике на ячейку contract_link"""
        # Проверяем, что кликнули на колонку contract_link
        contract_link_col = FIELD_ORDER.index('contract_link')
        if column != contract_link_col:
            return
        
        item = self.manual_nmcc_table.item(row, column)
        if item:
            url = item.data(Qt.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))
    
    def show_row_details_dialog(self, row_data_dict):
        """Показ модального окна с детальными данными строки в табличном виде"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Детали позиции")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        # Создаем таблицу с параметрами и значениями
        details_table = QTableWidget()
        details_table.setColumnCount(2)
        details_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        details_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        details_table.verticalHeader().setVisible(False)
        details_table.setAlternatingRowColors(True)
        
        # Заполняем таблицу данными
        row_num = 0
        for field_name in FIELD_ORDER:
            value = row_data_dict.get(field_name, "")
            if value:  # Показываем только непустые значения
                details_table.insertRow(row_num)
                
                # Параметр (название столбца)
                param_item = QTableWidgetItem(EXPORT_HEADERS_RU.get(field_name, field_name))
                param_item.setFlags(param_item.flags() & ~Qt.ItemIsEditable)
                param_item.setForeground(Qt.darkGray)
                details_table.setItem(row_num, 0, param_item)
                
                # Значение
                # Для contract_link создаем кликабельную ссылку
                if field_name == 'contract_link' and value:
                    value_item = QTableWidgetItem(value)
                    value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                    # Делаем текст синим и подчеркнутым как hyperlink
                    font = value_item.font()
                    font.setUnderline(True)
                    font.setBold(True)
                    value_item.setFont(font)
                    value_item.setForeground(Qt.blue)
                    # Сохраняем URL в data role для открытия
                    value_item.setData(Qt.UserRole, value)
                    # Устанавливаем курсор-руку при наведении
                    value_item.setFlags(value_item.flags() | Qt.ItemIsUserCheckable)
                else:
                    value_item = QTableWidgetItem(str(value))
                    value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                details_table.setItem(row_num, 1, value_item)
                
                row_num += 1
        
        # Устанавливаем ширину первой колонки
        details_table.setColumnWidth(0, 250)
        
        # Обработка двойного клика по ссылке в модальном окне
        def on_details_table_double_click(row, column):
            if column == 1:  # Колонка "Значение"
                item = details_table.item(row, column)
                if item:
                    url = item.data(Qt.UserRole)
                    if url:
                        QDesktopServices.openUrl(QUrl(url))
        
        details_table.cellDoubleClicked.connect(on_details_table_double_click)
        
        layout.addWidget(details_table)
        
        # Кнопка "Добавить в НМЦК"
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        add_to_nmcc_btn = QPushButton("Добавить в НМЦК")
        add_to_nmcc_btn.setToolTip("Добавить эту позицию в таблицу НМЦК ручной подбор")
        add_to_nmcc_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 16px; font-weight: bold;")
        
        def on_add_to_nmcc():
            self.add_row_to_manual_nmcc_table(row_data_dict)
            dialog.accept()
        
        add_to_nmcc_btn.clicked.connect(on_add_to_nmcc)
        btn_layout.addWidget(add_to_nmcc_btn)
        
        # Кнопка закрытия
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        
        dialog.exec_()
    
    def add_row_to_manual_nmcc_table(self, row_data: dict):
        """Добавление строки данных в таблицу НМЦК ручной подбор"""
        row_position = self.manual_nmcc_table.rowCount()
        self.manual_nmcc_table.insertRow(row_position)
        
        # Сохраняем номер реестровой записи для подсветки дубликатов
        reestr_number = row_data.get('reestr_number', '')
        
        for col_idx, field_name in enumerate(FIELD_ORDER):
            value = row_data.get(field_name, "")
            
            # Для колонки contract_link создаем кликабельную ссылку
            if field_name == 'contract_link' and value:
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                font = item.font()
                font.setUnderline(True)
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.blue)
                item.setData(Qt.UserRole, value)
            else:
                item = QTableWidgetItem(str(value) if value else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            
            self.manual_nmcc_table.setItem(row_position, col_idx, item)
        
        # Переключаемся на вкладку НМЦК ручной подбор
        tab_index = self.tables_tab_widget.indexOf(self.manual_nmcc_tab)
        if tab_index >= 0:
            self.tables_tab_widget.setCurrentIndex(tab_index)
        
        # Обновляем итоговые данные после добавления позиции
        self.update_manual_nmcc_summary()
        
        # Обновляем подсветку дубликатов
        if reestr_number:
            self.highlight_duplicates_in_final_table({reestr_number}, 'manual_nmcc')
        
        self.append_log(f"Позиция добавлена в НМЦК ручной подбор: {row_data.get('name', 'Без названия')}")
    
    def calculate_nmcc_by_volume(self):
        """Расчет НМЦК по объему: найти 3 позиции с количеством, наиболее близким к указанному объему
        
        Логика:
        1. Берем все значения из столбца "кол-во в потреб. единицах измерения"
        2. Приводим их к числу (обрабатываем запятые, пробелы как разделители тысяч)
        3. Сравниваем с целевым объемом через абсолютную разницу
        4. Выводим 3 наиболее близких значения (по возрастанию дельты)
        
        Пример: при вводе 8000 из значений [1000, 2500, 5000, 8500, 10000]
        дельты: |1000-8000|=7000, |2500-8000|=5500, |5000-8000|=3000, |8500-8000|=500, |10000-8000|=2000
        будут выбраны: 8500 (дельта 500), 10000 (дельта 2000), 5000 (дельта 3000)
        """
        try:
            # Получаем объем из поля ввода
            volume_str = self.nmcc_volume_input.text().strip()
            if not volume_str:
                QMessageBox.warning(self, "Внимание", "Введите объем в ед. измерения")
                return
            
            target_volume = float(volume_str.replace(',', '.'))
            
            # Находим индекс колонки qty_consumption_unit
            qty_col_index = FIELD_ORDER.index('qty_consumption_unit')
            
            # Собираем все видимые строки из итоговой таблицы с корректными числовыми значениями
            rows_with_qty = []
            for row in range(self.results_table.rowCount()):
                if not self.results_table.isRowHidden(row):
                    item = self.results_table.item(row, qty_col_index)
                    if item and item.text():
                        try:
                            # Очищаем значение от лишних символов и приводим к float
                            qty_text = item.text().strip().replace(',', '.')
                            # Удаляем возможные пробелы как разделители тысяч (например "1 000" -> "1000")
                            qty_text = qty_text.replace(' ', '')
                            qty = float(qty_text)
                            rows_with_qty.append((row, qty))
                        except ValueError:
                            # Пропускаем строки с некорректными числовыми данными
                            continue
            
            if len(rows_with_qty) < 3:
                QMessageBox.warning(self, "Внимание", f"Недостаточно данных для расчета. Найдено позиций: {len(rows_with_qty)}, требуется минимум 3")
                return
            
            # Сортируем по абсолютной дельте между объемом в таблице и целевым объемом
            # Это обеспечивает выбор наиболее близких значений независимо от того, больше они или меньше
            rows_with_qty.sort(key=lambda x: abs(x[1] - target_volume))
            
            # Берем 3 наиболее близких значения
            top_3_rows = rows_with_qty[:3]
            
            # Заполняем таблицу НМЦК отобранными строками
            self.fill_nmcc_table(top_3_rows)
            
            # Окрашиваем периметр кнопки в зеленый цвет
            self.nmcc_volume_btn.setStyleSheet("border: 3px solid green;")
            # Сбрасываем стиль у других кнопок
            self.nmcc_avg_btn.setStyleSheet("")
            self.nmcc_optimal_btn.setStyleSheet("")
            
            # Переключаемся на вкладку НМЦК
            self.tables_tab_widget.setCurrentIndex(1)
            
            # Формируем подробное сообщение о результатах
            selected_volumes = [f"{row[1]:.2f}" for row in top_3_rows]
            self.append_log(f"НМЦК по объему: целевой объем={target_volume}, выбрано 3 позиции: {', '.join(selected_volumes)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при расчете НМЦК по объему: {e}")
            logging.error(f"Ошибка calculate_nmcc_by_volume: {e}", exc_info=True)
    
    def calculate_nmcc_by_avg_price(self):
        """Расчет НМЦК приближенный к КП: найти 3 позиции со средней ценой, наиболее близкой к средней по введенным КП"""
        try:
            # Получаем цены из полей ввода
            prices = []
            for input_field in [self.nmcc_price1_input, self.nmcc_price2_input, self.nmcc_price3_input]:
                price_str = input_field.text().strip()
                if price_str:
                    try:
                        prices.append(float(price_str.replace(',', '.')))
                    except ValueError:
                        continue
            
            if len(prices) == 0:
                QMessageBox.warning(self, "Внимание", "Введите хотя бы одну цену за ед. измерения по КП")
                return
            
            # Вычисляем среднюю арифметическую по введенным КП
            avg_price_kp = sum(prices) / len(prices)
            
            # Находим индекс колонки price_per_unit
            price_col_index = FIELD_ORDER.index('price_per_unit')
            
            # Собираем все видимые строки из итоговой таблицы
            rows_with_price = []
            for row in range(self.results_table.rowCount()):
                if not self.results_table.isRowHidden(row):
                    item = self.results_table.item(row, price_col_index)
                    if item and item.text():
                        try:
                            price = float(item.text().replace(',', '.'))
                            rows_with_price.append((row, price))
                        except ValueError:
                            continue
            
            if len(rows_with_price) < 3:
                QMessageBox.warning(self, "Внимание", f"Недостаточно данных для расчета. Найдено позиций: {len(rows_with_price)}, требуется минимум 3")
                return
            
            # Сортируем по дельте (разнице) между ценой в таблице и средней ценой КП
            rows_with_price.sort(key=lambda x: abs(x[1] - avg_price_kp))
            
            # Берем 3 наиболее близких
            top_3_rows = rows_with_price[:3]
            
            # Заполняем таблицу НМЦК
            self.fill_nmcc_table(top_3_rows)
            
            # Окрашиваем периметр кнопки в зеленый цвет
            self.nmcc_avg_btn.setStyleSheet("border: 3px solid green;")
            # Сбрасываем стиль у других кнопок
            self.nmcc_volume_btn.setStyleSheet("")
            self.nmcc_optimal_btn.setStyleSheet("")
            
            # Переключаемся на вкладку НМЦК
            self.tables_tab_widget.setCurrentIndex(1)
            
            self.append_log(f"НМЦК по средней цене КП: средняя цена={avg_price_kp:.2f}₽, выбрано 3 позиции")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при расчете НМЦК по средней цене: {e}")
            logging.error(f"Ошибка calculate_nmcc_by_avg_price: {e}", exc_info=True)
    
    def calculate_nmcc_optimal(self):
        """Оптимальный алгоритм расчета НМЦК:
        
        Логика:
        1. В приоритете 'вписаться в цену' - средняя цена ЕИС должна быть >= средней цены КП
        2. Не допускать значительного разброса по объему (макс. отклонение <= 50%)
        3. Использовать комбинированный скоринг для баланса между ценой и объемом
        
        Алгоритм:
        - Для каждой позиции вычисляем скоринг на основе:
          * Ценовой фактор: насколько цена близка к целевой (с бонусом за EIS >= KP)
          * Объемный фактор: насколько объем близок к целевому (с штрафом за >50% отклонение)
        - Отбираем 3 позиции с наилучшим综合ным скорингом
        """
        try:
            # Получаем целевые значения
            volume_str = self.nmcc_volume_input.text().strip()
            if not volume_str:
                QMessageBox.warning(self, "Внимание", "Введите объем в ед. измерения для оптимального расчета")
                return
            
            target_volume = float(volume_str.replace(',', '.'))
            
            prices = []
            for input_field in [self.nmcc_price1_input, self.nmcc_price2_input, self.nmcc_price3_input]:
                price_str = input_field.text().strip()
                if price_str:
                    try:
                        prices.append(float(price_str.replace(',', '.')))
                    except ValueError:
                        continue
            
            if len(prices) == 0:
                QMessageBox.warning(self, "Внимание", "Введите хотя бы одну цену за ед. измерения по КП")
                return
            
            avg_price_kp = sum(prices) / len(prices)
            
            # Находим индексы колонок
            price_col_index = FIELD_ORDER.index('price_per_unit')
            qty_col_index = FIELD_ORDER.index('qty_consumption_unit')
            
            # Собираем все видимые строки с данными о цене и объеме
            rows_with_data = []
            for row in range(self.results_table.rowCount()):
                if not self.results_table.isRowHidden(row):
                    price_item = self.results_table.item(row, price_col_index)
                    qty_item = self.results_table.item(row, qty_col_index)
                    
                    if price_item and price_item.text() and qty_item and qty_item.text():
                        try:
                            price = float(price_item.text().replace(',', '.'))
                            qty_text = qty_item.text().strip().replace(',', '.').replace(' ', '')
                            qty = float(qty_text)
                            rows_with_data.append((row, price, qty))
                        except ValueError:
                            continue
            
            if len(rows_with_data) < 3:
                QMessageBox.warning(self, "Внимание", f"Недостаточно данных для расчета. Найдено позиций: {len(rows_with_data)}, требуется минимум 3")
                return
            
            # Вычисляем скоринг для каждой позиции
            scored_rows = []
            for row_idx, price, qty in rows_with_data:
                # 1. Ценовой скоринг (0-100 баллов)
                # Базовый скоринг: обратная пропорциональность дельте цены
                price_delta = abs(price - avg_price_kp)
                price_diff_score = max(0, 100 - (price_delta / max(avg_price_kp, 0.01)) * 100)
                
                # Бонус за EIS >= KP (вписаться в цену)
                if price >= avg_price_kp:
                    price_bonus = 50  # Дополнительный бонус за выполнение приоритета
                else:
                    price_bonus = 0
                
                price_score = price_diff_score + price_bonus
                
                # 2. Объемный скоринг (0-100 баллов)
                volume_delta = abs(qty - target_volume)
                volume_diff_percent = (volume_delta / max(target_volume, 0.01)) * 100
                
                # Штраф за превышение 50% отклонения
                if volume_diff_percent <= 50:
                    volume_score = 100 - volume_diff_percent  # 50-100 баллов при отклонении 0-50%
                else:
                    volume_score = max(0, 100 - volume_diff_percent * 2)  # Агрессивный штраф за >50%
                
                # 3. Комбинированный скоринг
                # Приоритет цены (60%) над объемом (40%) для выполнения требования "вписаться в цену"
                combined_score = price_score * 0.6 + volume_score * 0.4
                
                scored_rows.append((row_idx, price, qty, combined_score, price_score, volume_score))
            
            # Сортируем по комбинированному скорингу (по убыванию)
            scored_rows.sort(key=lambda x: x[3], reverse=True)
            
            # Берем 3 позиции с наилучшим скорингом
            top_3_rows = [(r[0], r[1]) for r in scored_rows[:3]]  # (row_index, price) для fill_nmcc_table
            
            # Заполняем таблицу НМЦК
            self.fill_nmcc_table(top_3_rows)
            
            # Окрашиваем периметр кнопки в зеленый цвет
            self.nmcc_optimal_btn.setStyleSheet("border: 3px solid green;")
            # Сбрасываем стиль у других кнопок
            self.nmcc_volume_btn.setStyleSheet("")
            self.nmcc_avg_btn.setStyleSheet("")
            
            # Переключаемся на вкладку НМЦК
            self.tables_tab_widget.setCurrentIndex(1)
            
            # Формируем подробное сообщение о результатах
            selected_info = [f"цена={r[1]:.2f}₽, объем={r[2]:.2f}, скор={r[3]:.1f}" 
                          for r in scored_rows[:3]]
            self.append_log(f"НМЦК Оптимальный: средняя цена КП={avg_price_kp:.2f}₽, целевой объем={target_volume}")
            self.append_log(f"Выбрано 3 позиции: {'; '.join(selected_info)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при оптимальном расчете НМЦК: {e}")
            logging.error(f"Ошибка calculate_nmcc_optimal: {e}", exc_info=True)
    
    def fill_nmcc_table(self, row_indices):
        """Заполнение таблицы НМЦК данными из указанных строк итоговой таблицы
        
        Args:
            row_indices: список кортежей (row_index, value) где value - значение по которому сортировали
        """
        # Очищаем таблицу НМЦК
        self.nmcc_table.setRowCount(0)
        
        # Собираем номера реестровых записей для подсветки дубликатов
        reestr_numbers_in_nmcc = set()
        
        for row_idx, _ in row_indices:
            new_row = self.nmcc_table.rowCount()
            self.nmcc_table.insertRow(new_row)
            
            for col_idx, field_name in enumerate(FIELD_ORDER):
                source_item = self.results_table.item(row_idx, col_idx)
                if source_item:
                    value = source_item.text()
                    
                    # Сохраняем номер реестровой записи для проверки дубликатов
                    if field_name == 'reestr_number' and value:
                        reestr_numbers_in_nmcc.add(value)
                    
                    # Для колонки contract_link создаем кликабельную ссылку
                    if field_name == 'contract_link' and value:
                        item = QTableWidgetItem(value)
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        font = item.font()
                        font.setUnderline(True)
                        font.setBold(True)
                        item.setFont(font)
                        item.setForeground(Qt.blue)
                        item.setData(Qt.UserRole, value)
                    else:
                        item = QTableWidgetItem(value)
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    
                    self.nmcc_table.setItem(new_row, col_idx, item)
        
        # Обновляем подсветку дубликатов в итоговой таблице
        self.highlight_duplicates_in_final_table(reestr_numbers_in_nmcc, 'nmcc')
        
        # Обновляем итоговые данные после заполнения таблицы
        self.update_nmcc_summary()
    
    def update_nmcc_summary(self):
        """Расчет и обновление итоговых данных в блоке 'Итоговые данные' (вкладка НМЦК)"""
        try:
            # 1. Средняя цена по КП: (цена КП1 + цена КП2 + цена КП3) / 3
            prices = []
            for input_field in [self.nmcc_price1_input, self.nmcc_price2_input, self.nmcc_price3_input]:
                price_str = input_field.text().strip()
                if price_str:
                    try:
                        prices.append(float(price_str.replace(',', '.')))
                    except ValueError:
                        continue
            
            if len(prices) > 0:
                avg_kp = sum(prices) / len(prices)
                self.nmcc_avg_kp_label.setText(f"{avg_kp:.2f}")
            else:
                self.nmcc_avg_kp_label.setText("0.00")
            
            # 2. Средняя по ЕИС: сумма цен из таблицы "результат расчета НМЦК" / 3
            price_col_index = FIELD_ORDER.index('price_per_unit')
            eis_prices = []
            for row in range(self.nmcc_table.rowCount()):
                item = self.nmcc_table.item(row, price_col_index)
                if item and item.text():
                    try:
                        price = float(item.text().replace(',', '.'))
                        eis_prices.append(price)
                    except ValueError:
                        continue
            
            if len(eis_prices) > 0:
                avg_eis = sum(eis_prices) / len(eis_prices)
                self.nmcc_avg_eis_label.setText(f"{avg_eis:.2f}")
            else:
                self.nmcc_avg_eis_label.setText("0.00")
            
            # 3. Дельта средних цен: абсолютное и относительное отклонение
            # Дельта = средняя ЕИС - средняя КП (положительная = ЕИС выше, что хорошо для "вписаться в цену")
            if len(prices) > 0 and len(eis_prices) > 0:
                price_delta_abs = avg_eis - avg_kp
                if avg_kp != 0:
                    price_delta_percent = (price_delta_abs / avg_kp) * 100
                else:
                    price_delta_percent = 0.0
                self.nmcc_price_delta_label.setText(f"{price_delta_abs:.2f} ({price_delta_percent:.2f}%)")
            else:
                self.nmcc_price_delta_label.setText("0.00 (0.00%)")
            
            # 4. Максимальное отклонение по объему: абсолютное и относительное
            volume_str = self.nmcc_volume_input.text().strip()
            max_deviation_abs = 0.0
            max_deviation_percent = 0.0
            
            if volume_str:
                try:
                    target_volume = float(volume_str.replace(',', '.'))
                    
                    qty_col_index = FIELD_ORDER.index('qty_consumption_unit')
                    
                    for row in range(self.nmcc_table.rowCount()):
                        item = self.nmcc_table.item(row, qty_col_index)
                        if item and item.text():
                            try:
                                qty_text = item.text().strip().replace(',', '.').replace(' ', '')
                                qty = float(qty_text)
                                
                                # Дельта = |объем - количество|
                                delta = abs(target_volume - qty)
                                
                                # Процент отклонения = (дельта / объем) * 100
                                if target_volume != 0:
                                    deviation_percent = (delta / target_volume) * 100
                                    if deviation_percent > max_deviation_percent:
                                        max_deviation_percent = deviation_percent
                                        max_deviation_abs = delta
                            except ValueError:
                                continue
                    
                    self.nmcc_max_deviation_label.setText(f"{max_deviation_abs:.2f} ({max_deviation_percent:.2f}%)")
                except ValueError:
                    self.nmcc_max_deviation_label.setText("0.00 (0.00%)")
            else:
                self.nmcc_max_deviation_label.setText("0.00 (0.00%)")
                
        except Exception as e:
            logging.error(f"Ошибка update_nmcc_summary: {e}", exc_info=True)
            self.nmcc_avg_kp_label.setText("0.00")
            self.nmcc_avg_eis_label.setText("0.00")
            self.nmcc_price_delta_label.setText("0.00 (0.00%)")
            self.nmcc_max_deviation_label.setText("0.00 (0.00%)")

    def update_manual_nmcc_summary(self):
        """Расчет и обновление итоговых данных в блоке 'Итоговые данные' (вкладка НМЦК ручной подбор)"""
        try:
            # 1. Средняя цена по КП: (цена КП1 + цена КП2 + цена КП3) / 3
            prices = []
            for input_field in [self.manual_nmcc_price1_input, self.manual_nmcc_price2_input, self.manual_nmcc_price3_input]:
                price_str = input_field.text().strip()
                if price_str:
                    try:
                        prices.append(float(price_str.replace(',', '.')))
                    except ValueError:
                        continue
            
            if len(prices) > 0:
                avg_kp = sum(prices) / len(prices)
                self.manual_nmcc_avg_kp_label.setText(f"{avg_kp:.2f}")
            else:
                self.manual_nmcc_avg_kp_label.setText("0.00")
            
            # 2. Средняя по ЕИС: сумма цен из таблицы "Позиции для НМЦК (ручной подбор)" / 3
            price_col_index = FIELD_ORDER.index('price_per_unit')
            eis_prices = []
            for row in range(self.manual_nmcc_table.rowCount()):
                item = self.manual_nmcc_table.item(row, price_col_index)
                if item and item.text():
                    try:
                        price = float(item.text().replace(',', '.'))
                        eis_prices.append(price)
                    except ValueError:
                        continue
            
            if len(eis_prices) > 0:
                avg_eis = sum(eis_prices) / len(eis_prices)
                self.manual_nmcc_avg_eis_label.setText(f"{avg_eis:.2f}")
            else:
                self.manual_nmcc_avg_eis_label.setText("0.00")
            
            # 3. Дельта средних цен: абсолютное и относительное отклонение
            if len(prices) > 0 and len(eis_prices) > 0:
                price_delta_abs = avg_eis - avg_kp
                if avg_kp != 0:
                    price_delta_percent = (price_delta_abs / avg_kp) * 100
                else:
                    price_delta_percent = 0.0
                self.manual_nmcc_price_delta_label.setText(f"{price_delta_abs:.2f} ({price_delta_percent:.2f}%)")
            else:
                self.manual_nmcc_price_delta_label.setText("0.00 (0.00%)")
            
            # 4. Максимальное отклонение по объему: абсолютное и относительное
            volume_str = self.manual_nmcc_volume_input.text().strip()
            max_deviation_abs = 0.0
            max_deviation_percent = 0.0
            
            if volume_str:
                try:
                    target_volume = float(volume_str.replace(',', '.'))
                    
                    qty_col_index = FIELD_ORDER.index('qty_consumption_unit')
                    
                    for row in range(self.manual_nmcc_table.rowCount()):
                        item = self.manual_nmcc_table.item(row, qty_col_index)
                        if item and item.text():
                            try:
                                qty_text = item.text().strip().replace(',', '.').replace(' ', '')
                                qty = float(qty_text)
                                
                                # Дельта = |объем - количество|
                                delta = abs(target_volume - qty)
                                
                                # Процент отклонения = (дельта / объем) * 100
                                if target_volume != 0:
                                    deviation_percent = (delta / target_volume) * 100
                                    if deviation_percent > max_deviation_percent:
                                        max_deviation_percent = deviation_percent
                                        max_deviation_abs = delta
                            except ValueError:
                                continue
                    
                    self.manual_nmcc_max_deviation_label.setText(f"{max_deviation_abs:.2f} ({max_deviation_percent:.2f}%)")
                except ValueError:
                    self.manual_nmcc_max_deviation_label.setText("0.00 (0.00%)")
            else:
                self.manual_nmcc_max_deviation_label.setText("0.00 (0.00%)")
                
        except Exception as e:
            logging.error(f"Ошибка update_manual_nmcc_summary: {e}", exc_info=True)
            self.manual_nmcc_avg_kp_label.setText("0.00")
            self.manual_nmcc_avg_eis_label.setText("0.00")
            self.manual_nmcc_price_delta_label.setText("0.00 (0.00%)")
            self.manual_nmcc_max_deviation_label.setText("0.00 (0.00%)")

    # Методы для синхронизации полей ввода НМЦК между вкладками
    def sync_nmcc_price1(self, text):
        """Синхронизация поля цены 1 из вкладки НМЦК во вкладку ручной подбор"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.manual_nmcc_price1_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_nmcc_price2(self, text):
        """Синхронизация поля цены 2 из вкладки НМЦК во вкладку ручной подбор"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.manual_nmcc_price2_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_nmcc_price3(self, text):
        """Синхронизация поля цены 3 из вкладки НМЦК во вкладку ручной подбор"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.manual_nmcc_price3_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_nmcc_volume(self, text):
        """Синхронизация поля объема из вкладки НМЦК во вкладку ручной подбор"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.manual_nmcc_volume_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_manual_nmcc_price1(self, text):
        """Синхронизация поля цены 1 из вкладки ручной подбор во вкладку НМЦК"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.nmcc_price1_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_manual_nmcc_price2(self, text):
        """Синхронизация поля цены 2 из вкладки ручной подбор во вкладку НМЦК"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.nmcc_price2_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_manual_nmcc_price3(self, text):
        """Синхронизация поля цены 3 из вкладки ручной подбор во вкладку НМЦК"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.nmcc_price3_input.setText(text)
            self._syncing_nmcc_fields = False
    
    def sync_manual_nmcc_volume(self, text):
        """Синхронизация поля объема из вкладки ручной подбор во вкладку НМЦК"""
        if not self._syncing_nmcc_fields:
            self._syncing_nmcc_fields = True
            self.nmcc_volume_input.setText(text)
            self._syncing_nmcc_fields = False

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

    def show_help(self):
        """Показать инструкцию по работе с программой"""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Инструкция по работе с программой")
        help_dialog.setMinimumSize(700, 600)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Создаем QTextEdit для отображения текста инструкции с прокруткой
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2 style="color: #0066cc;">Инструкция по работе с Универсальным парсером ЕИС</h2>
        
        <h3>1. Начало работы</h3>
        <p><b>1.1.</b> Загрузите базу данных МНН, нажав кнопку "База данных" в левой панели и выбрав файл 
        <code>esklp_smnn_*.xlsx</code>. После загрузки станет доступен автокомплит для МНН, форм выпуска и дозировок.</p>
        
        <h3>2. Поиск и парсинг данных</h3>
        <p><b>2.1.</b> Введите поисковый запрос (МНН) в поле "Поисковый запрос". При загруженной базе данных 
        будет работать автодополнение.</p>
        <p><b>2.2.</b> При необходимости установите даты поиска в полях "С" и "По".</p>
        <p><b>2.3.</b> Выберите фильтры:</p>
        <ul>
            <li><b>Только Москва</b> — поиск только по контрактам Москвы и МО</li>
            <li><b>Только Росунимед</b> — поиск только по контрактам РОСУНИМЕД</li>
        </ul>
        <p><b>2.4.</b> Установите фильтры по МНН, форме выпуска и дозировке (доступны при загруженной базе данных).</p>
        <p><b>2.5.</b> Нажмите кнопку "Старт" для начала парсинга.</p>
        <p><b>2.6.</b> Результаты будут отображаться во вкладке "Итоговая" в виде таблицы.</p>
        
        <h3>3. Работа с результатами</h3>
        <p><b>3.1.</b> Таблица результатов содержит все найденные позиции. Двойной клик по ссылке в колонке 
        "Контракт (ссылка)" откроет её в браузере.</p>
        <p><b>3.2.</b> Используйте фильтры для отбора нужных позиций по МНН, форме выпуска и дозировке.</p>
        <p><b>3.3.</b> Для выгрузки данных нажмите "Выгрузить в Excel" или "Выгрузить в CSV".</p>
        
        <h3>4. Расчет НМЦК</h3>
        <p>Вкладка "НМЦК" предназначена для расчета начальной максимальной цены контракта.</p>
        <p><b>4.1.</b> Введите данные для расчета в блок "Ввод данных для расчета НМЦК":</p>
        <ul>
            <li>Цена за ед. измерения по 1, 2, 3 КП (коммерческим предложениям)</li>
            <li>Объем в ед. измерения (требуемое количество)</li>
        </ul>
        <p><b>4.2.</b> Используйте кнопки расчета:</p>
        <ul>
            <li><b>НМЦК по объему</b> — находит 3 позиции с количеством, наиболее близким к указанному объему</li>
            <li><b>НМЦК приближенный к КП</b> — находит 3 позиции со средней ценой, наиболее близкой к средней по введенным КП</li>
            <li><b>НМЦК Оптимальный</b> — оптимальный алгоритм с приоритетом "вписаться в цену" и минимизацией разброса по объему</li>
        </ul>
        <p><b>4.3.</b> Результаты расчета отображаются в таблице "Результат расчета НМЦК (3 позиции)".</p>
        <p><b>4.4.</b> Блок "Итоговые данные" показывает:</p>
        <ul>
            <li>Средняя цена по КП</li>
            <li>Средняя по ЕИС</li>
            <li>Дельта средних цен (абсолютная и процентная)</li>
            <li>Макс. отклонение по объему (абсолютное и процентное)</li>
        </ul>
        
        <h3>5. НМЦК ручной подбор</h3>
        <p>Вкладка "НМЦК ручной подбор" позволяет вручную формировать список позиций для НМЦК.</p>
        <p><b>5.1.</b> Двойной клик по строке в таблице результатов добавляет позицию в таблицу ручного подбора.</p>
        <p><b>5.2.</b> Поля ввода данных синхронизированы между вкладками "НМЦК" и "НМЦК ручной подбор".</p>
        
        <h3>6. Настройки</h3>
        <p>Во вкладке "Настройки" можно изменить параметры парсинга:</p>
        <ul>
            <li>Максимум контрактов — целевое количество контрактов для сбора</li>
            <li>Таймаут ожидания (мс) — время ожидания загрузки страниц</li>
            <li>Раунды раскрытия — количество раундов раскрытия списков</li>
            <li>Задержка загрузки страницы (мс)</li>
            <li>Задержка раскрытия (мс)</li>
        </ul>
        
        <h3>7. Сброс данных</h3>
        <p>Кнопка "Сброс" очищает:</p>
        <ul>
            <li>Все данные из таблиц результатов</li>
            <li>Список найденных ссылок</li>
            <li>Лог выполнения</li>
            <li>Поля ввода НМЦК</li>
            <li>Индикацию кнопок расчета НМЦК</li>
            <li>Поисковый запрос и фильтры</li>
        </ul>
        
        <h3>8. Меню</h3>
        <p><b>Файл → Выход</b> — закрытие приложения.</p>
        <p><b>Помощь → О программе</b> — информация о программе.</p>
        <p><b>Помощь → Инструкция</b> — открытие этого окна.</p>
        
        <hr>
        <p style="color: #666; font-size: 11px;"><i>Для дополнительной информации обратитесь к разработчику.</i></p>
        """)
        
        layout.addWidget(help_text)
        
        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.setFixedWidth(120)
        close_button.clicked.connect(help_dialog.close)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        help_dialog.setLayout(layout)
        help_dialog.exec_()

    def load_reference_database(self):
        """Загрузка базы данных МНН, формы выпуска и дозировки из файла esklp_smnn_*.xlsx в отдельном потоке"""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.critical(self, "Ошибка", "Библиотека openpyxl не установлена.\nУстановите: pip install openpyxl")
            return
        
        # Запрашиваем путь к файлу через диалог
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл базы данных",
            "",
            "Excel файлы (*.xlsx);;Все файлы (*.*)"
        )
        
        if not file_path:
            return  # Пользователь отменил выбор
        
        # Блокируем кнопку на время загрузки
        self.load_db_button.setEnabled(False)
        self.load_db_button.setText("ЗАГРУЗКА...")
        self.append_log(f"Загрузка базы данных из: {file_path}")
        
        # Создаем и запускаем поток для загрузки
        # Важно: сохраняем ссылку на поток, чтобы он не был уничтожен сборщиком мусора
        self.db_loader_thread = DatabaseLoaderWorker(file_path)
        self.db_loader_thread.finished.connect(self.on_database_loaded)
        self.db_loader_thread.error.connect(self.on_database_error)
        # Добавляем обработчик завершения для разблокировки кнопки (на случай ошибки)
        self.db_loader_thread.finished.connect(lambda: self.load_db_button.setEnabled(True))
        self.db_loader_thread.finished.connect(lambda: self.load_db_button.setText('База данных'))
        self.db_loader_thread.error.connect(lambda: self.load_db_button.setEnabled(True))
        self.db_loader_thread.error.connect(lambda: self.load_db_button.setText('База данных'))
        self.db_loader_thread.start()
    
    def on_database_loaded(self, reference_data, rows_loaded):
        """Обработка успешной загрузки базы данных"""
        self.reference_data = reference_data
        self.append_log(f"База данных загружена: {rows_loaded} записей")
        
        # Извлекаем уникальные МНН для автокомплита
        self.mnn_list = list(set(item['mnn'] for item in reference_data if item['mnn']))
        self.mnn_list.sort()
        self.mnn_model.setStringList(self.mnn_list)
        
        # Устанавливаем модель автокомплита для всех ComboBox
        self.search_input.setModel(self.mnn_model)
        self.search_input.completer().setModel(self.mnn_model)
        self.search_input.completer().setCompletionMode(QCompleter.PopupCompletion)
        
        self.filter_result_input.setModel(self.mnn_model)
        self.filter_result_input.completer().setModel(self.mnn_model)
        self.filter_result_input.completer().setCompletionMode(QCompleter.PopupCompletion)
        
        # Формируем словари форм выпуска и дозировок по МНН
        self.forms_for_mnn = {}
        self.doses_for_mnn = {}
        self.doses_for_mnn_form = {}  # doses_for_mnn_form[mnn][form] = [doses]
        for item in reference_data:
            mnn = item['mnn']
            form = item['release_form']
            dose = item['dose']
            
            if mnn not in self.forms_for_mnn:
                self.forms_for_mnn[mnn] = set()
            if mnn not in self.doses_for_mnn:
                self.doses_for_mnn[mnn] = set()
            if mnn not in self.doses_for_mnn_form:
                self.doses_for_mnn_form[mnn] = {}
            
            if form:
                self.forms_for_mnn[mnn].add(form)
                if form not in self.doses_for_mnn_form[mnn]:
                    self.doses_for_mnn_form[mnn][form] = set()
                if dose:
                    self.doses_for_mnn_form[mnn][form].add(dose)
            
            if dose:
                self.doses_for_mnn[mnn].add(dose)
        
        # Преобразуем множества в отсортированные списки
        for mnn in self.forms_for_mnn:
            self.forms_for_mnn[mnn] = sorted(list(self.forms_for_mnn[mnn]))
        for mnn in self.doses_for_mnn:
            self.doses_for_mnn[mnn] = sorted(list(self.doses_for_mnn[mnn]))
        for mnn in self.doses_for_mnn_form:
            for form in self.doses_for_mnn_form[mnn]:
                self.doses_for_mnn_form[mnn][form] = sorted(list(self.doses_for_mnn_form[mnn][form]))
        
        # Подключаем обработчики для автозаполнения форм и дозировок
        self.search_input.lineEdit().textChanged.connect(self.on_search_text_changed)
        self.filter_result_input.lineEdit().textChanged.connect(self.on_filter_mnn_changed)
        self.filter_form_input.lineEdit().textChanged.connect(self.on_filter_form_changed)
        
        # Обновляем индикатор статуса базы данных
        self.db_status_indicator.setStyleSheet("background-color: green; border-radius: 6px;")
        self.db_status_indicator.setToolTip("База данных загружена")
        
        QMessageBox.information(self, "Успех", 
            f"База данных успешно загружена!\n"
            f"Записей: {rows_loaded}\n"
            f"Уникальных МНН: {len(self.mnn_list)}\n\n"
            f"Теперь доступен автокомплит для МНН, форм выпуска и дозировок.")
        # Кнопка будет разблокирована через connected сигналы
    
    def on_database_error(self, error_msg):
        """Обработка ошибки загрузки базы данных"""
        logging.error(f"Ошибка загрузки базы данных: {error_msg}")
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить базу данных:\n{error_msg}")
        # Кнопка будет разблокирована через connected сигналы
    
    def on_search_text_changed(self, text):
        """Обработка изменения текста в поле поискового запроса"""
        # Автоматически копируем выбранное МНН в фильтр по МНН
        if text in self.mnn_list:
            self.filter_result_input.setCurrentText(text)
            self.update_forms_and_doses(text)
    
    def on_filter_mnn_changed(self, text):
        """Обработка изменения текста в фильтре по МНН"""
        if text in self.mnn_list:
            self.update_forms_and_doses(text)
    
    def on_filter_form_changed(self, form):
        """Обработка изменения текста в фильтре по форме выпуска"""
        # Получаем текущее МНН
        mnn = self.filter_result_input.currentText().strip()
        if mnn in self.mnn_list and form:
            # Обновляем дозировки только для выбранной формы
            self.update_forms_and_doses(mnn, form)
    
    def update_forms_and_doses(self, mnn, form=None):
        """Обновление списков форм выпуска и дозировок для выбранного МНН"""
        # Обновляем список форм выпуска
        forms = self.forms_for_mnn.get(mnn, [])
        
        # Сохраняем текущий текст в поле формы
        current_form_text = self.filter_form_input.currentText()
        
        # Очищаем и заполняем заново
        self.filter_form_input.blockSignals(True)
        self.filter_form_input.clear()
        for f in forms:
            self.filter_form_input.addItem(f)
        self.filter_form_input.blockSignals(False)
        
        # Восстанавливаем текст, если он был
        if current_form_text:
            self.filter_form_input.setCurrentText(current_form_text)
        
        # Если форма не передана, обновляем все дозировки для МНН
        # Если форма передана - обновляем дозировки только для этой формы
        if form:
            doses = self.doses_for_mnn_form.get(mnn, {}).get(form, [])
        else:
            doses = self.doses_for_mnn.get(mnn, [])
        
        # Сохраняем текущий текст в поле дозировки
        current_dose_text = self.filter_dose_input.currentText()
        
        # Очищаем и заполняем заново
        self.filter_dose_input.blockSignals(True)
        self.filter_dose_input.clear()
        for d in doses:
            self.filter_dose_input.addItem(d)
        self.filter_dose_input.blockSignals(False)
        
        # Восстанавливаем текст, если он был
        if current_dose_text:
            self.filter_dose_input.setCurrentText(current_dose_text)


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
            expand_delay=800,
            results_table=None
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
