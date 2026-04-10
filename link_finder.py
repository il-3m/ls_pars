import sys
import time
import logging
import pandas as pd
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QDateEdit, QMessageBox, QProgressBar,
    QHBoxLayout, QTextEdit, QFileDialog, QDialog, 
    QGridLayout, QSpacerItem, QSizePolicy, 
    QComboBox, QCompleter, QFormLayout, QStatusBar,
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt5.QtCore import QDate, Qt, QThread, pyqtSignal, QStringListModel
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtCore import QUrl
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests

# Настройка логирования
logging.basicConfig(
    filename='parser_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


class LinkFinderWorker(QThread):
    """Поток для поиска ссылок на контракты"""
    update_progress = pyqtSignal(int)
    update_output = pyqtSignal(str)
    finished = pyqtSignal(list)
    links_found = pyqtSignal(str)

    def __init__(self, app, search_text, date_from, date_to, moscow_only, rosunimed_only, max_contracts):
        super().__init__()
        self.app = app
        self.search_text = search_text
        self.date_from = date_from
        self.date_to = date_to
        self.moscow_only = moscow_only
        self.rosunimed_only = rosunimed_only
        self.max_contracts = max_contracts
        self.driver = None

    def run(self):
        try:
            self.find_links()
        except Exception as e:
            self.update_output.emit(f"Ошибка: {str(e)}")
            logging.error(f"Ошибка в потоке: {str(e)}", exc_info=True)
        finally:
            if self.driver:
                self.driver.quit()
            self.finished.emit(self.app.found_links)

    def find_links(self):
        """Основной алгоритм поиска ссылок"""
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
            # Для customerIdOrg нужно полное кодирование (включая двоеточие)
            url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote)
        elif self.moscow_only:
            params["customerPlace"] = "77000000000,50000000000"
            params["customerPlaceCodes"] = "77000000000,50000000000"
            url = base_url + "?" + urllib.parse.urlencode(params, safe=':', quote_via=urllib.parse.quote)
        else:
            url = base_url + "?" + urllib.parse.urlencode(params, safe=':', quote_via=urllib.parse.quote)
        self.update_output.emit(f"Запрос: {url}")
        self.update_progress.emit(10)

        # Инициализация WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-gcm")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # Загрузка первой страницы с повторными попытками
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.driver.get(url)
                self.update_output.emit("Ожидание загрузки страницы...")
                self.update_progress.emit(20)
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
            # Формируем URL с учётом фильтра Росунимед
            if self.rosunimed_only:
                url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote)
            else:
                url = base_url + "?" + urllib.parse.urlencode(params, safe=':', quote_via=urllib.parse.quote)
            self.driver.get(url)
            self.update_output.emit(f"Страница {page}/{total_pages}")
            self.update_progress.emit(20 + (page * 60 // total_pages))

            # Извлечение всех ссылок
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
            original_links = [
                link.get_attribute("href")
                for link in links
                if link.get_attribute("href") and "contract/contractCard/common-info.html" in link.get_attribute("href")
            ]
            
            # Уникализация ссылок
            unique_links = list(set(original_links))
            self.update_output.emit(f"Найдено уникальных ссылок на странице: {len(unique_links)}")

            for i, original_link in enumerate(unique_links, 1):
                if contracts_count >= self.max_contracts:
                    break

                # Проверка на CAPTCHA
                if "captcha" in self.driver.page_source.lower():
                    self.update_output.emit("Обнаружена CAPTCHA!")
                    # Сигнал для главного потока о необходимости показать диалог
                    self.update_output.emit("Требуется ручное подтверждение...")
                    time.sleep(2)

                # Преобразование ссылки в целевой формат
                target_link = original_link.replace("common-info.html", "payment-info-and-target-of-order.html")
                
                # Извлечение номера реестра
                reestr_match = re.search(r'reestrNumber=([0-9]+)', target_link)
                if reestr_match:
                    reestr_number = reestr_match.group(1)
                    # Формируем ссылку в требуемом формате
                    final_link = f"https://zakupki.gov.ru/epz/contract/contractCard/payment-info-and-target-of-order.html?reestrNumber={reestr_number}"
                else:
                    final_link = target_link

                all_links.add(final_link)
                contracts_count += 1
                self.links_found.emit(f"Найдена ссылка: {final_link}")
                self.update_output.emit(f"Обработано контрактов: {contracts_count}/{self.max_contracts}")

        # Сохранение результатов
        if all_links:
            self.update_output.emit(f"Всего найдено ссылок: {len(all_links)}")
            self.app.found_links = list(all_links)
        else:
            self.update_output.emit("Ссылки не найдены.")
            self.app.found_links = []

        self.update_progress.emit(100)


class LogDialog(QDialog):
    """Диалог отображения логов"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Лог парсера")
        self.resize(800, 600)
        self.setModal(False)
        layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        self.setLayout(layout)
        self.log_history = []

    def append_log(self, text):
        self.log_history.append(text)
        self.log_text.append(text)


class LinkFinderApp(QMainWindow):
    """Основное приложение для поиска ссылок"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.thread = None
        self.found_links = []
        self.log_dialog = None
        self.mnn_list = []
        self.mnn_model = QStringListModel()

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle('Поиск ссылок для парсинга (ЕИС)')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QLabel { font-size: 14px; font-weight: bold; color: #333; }
            QLineEdit, QDateEdit, QComboBox { 
                font-size: 14px; padding: 8px; 
                border: 1px solid #ccc; border-radius: 5px; 
            }
            QPushButton { 
                font-size: 14px; padding: 10px; 
                background-color: #0078d4; color: white; 
                border: none; border-radius: 5px; 
            }
            QPushButton:hover { background-color: #005ea2; }
            QPushButton:disabled { background-color: #cccccc; }
            QCheckBox { font-size: 14px; color: #333; }
            QProgressBar { 
                border: 1px solid #ccc; border-radius: 5px; 
                text-align: center; font-size: 12px; 
            }
            QListWidget { 
                font-size: 12px; border: 1px solid #ccc; 
                border-radius: 5px; background-color: white;
            }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { 
                background-color: #0078d4; color: white; 
            }
            QListWidget::item:hover { background-color: #e5f3ff; }
        """)

        # Параметры поиска
        params_layout = QFormLayout()
        
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setPlaceholderText('Например: АЗИТРОМИЦИН')
        self.search_input.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.search_input.setInsertPolicy(QComboBox.NoInsert)

        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)

        self.max_contracts_input = QLineEdit()
        self.max_contracts_input.setText("20")
        self.max_contracts_input.setFixedWidth(60)

        params_layout.addRow(QLabel('Поисковый запрос (МНН):'), self.search_input)
        params_layout.addRow(QLabel('Дата с:'), self.date_from)
        params_layout.addRow(QLabel('Дата по:'), self.date_to)
        params_layout.addRow(QLabel('Макс. контрактов:'), self.max_contracts_input)

        # Фильтры
        filter_layout = QHBoxLayout()
        self.region_checkbox = QCheckBox('Искать только в Москве и МО')
        self.rosunimed_checkbox = QCheckBox('Искать только в Росунимеде')
        self.region_checkbox.toggled.connect(self.on_region_checkbox_toggled)
        self.rosunimed_checkbox.toggled.connect(self.on_rosunimed_checkbox_toggled)
        filter_layout.addWidget(self.region_checkbox)
        filter_layout.addWidget(self.rosunimed_checkbox)
        filter_layout.addStretch()

        # Кнопки
        button_layout = QHBoxLayout()
        self.load_db_button = QPushButton('Загрузить базу МНН')
        self.load_db_button.clicked.connect(self.load_database)
        self.search_button = QPushButton('Найти закупки')
        self.search_button.clicked.connect(self.start_search)
        self.export_button = QPushButton('Экспорт ссылок')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_links)
        self.copy_button = QPushButton('Копировать все')
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_all_links)
        
        button_layout.addWidget(self.load_db_button)
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.copy_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        # Разделитель для списка ссылок и лога
        splitter = QSplitter(Qt.Vertical)

        # Список найденных ссылок
        links_label = QLabel("Найденные ссылки для парсинга:")
        self.links_list = QListWidget()
        self.links_list.itemDoubleClicked.connect(self.open_link)
        
        links_widget = QWidget()
        links_layout = QVBoxLayout()
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.addWidget(links_label)
        links_layout.addWidget(self.links_list)
        links_widget.setLayout(links_layout)

        # Лог (скрыт по умолчанию, показывается через меню)
        log_widget = QWidget()
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 0)
        self.mini_log = QTextEdit()
        self.mini_log.setReadOnly(True)
        self.mini_log.setMaximumHeight(150)
        log_layout.addWidget(self.mini_log)
        log_widget.setLayout(log_layout)

        splitter.addWidget(links_widget)
        splitter.addWidget(log_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        # Статистика
        self.stats_layout = QHBoxLayout()
        self.total_links_label = QLabel("Всего ссылок: 0")
        self.stats_layout.addWidget(self.total_links_label)
        self.stats_layout.addStretch()

        # Основной макет
        main_layout.addLayout(params_layout)
        main_layout.addLayout(filter_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(splitter)
        main_layout.addLayout(self.stats_layout)

        central_widget.setLayout(main_layout)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_label = QLabel("Готов")
        self.statusBar.addPermanentWidget(self.status_label)

        # Меню
        self.create_menu()

    def create_menu(self):
        """Создание меню"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        export_action = file_menu.addAction("Экспорт ссылок")
        export_action.triggered.connect(self.export_links)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        # Меню Вид
        view_menu = menubar.addMenu("Вид")
        log_action = view_menu.addAction("Показать лог")
        log_action.triggered.connect(self.show_log_dialog)
        clear_action = view_menu.addAction("Очистить список")
        clear_action.triggered.connect(self.clear_links)

        # Меню Помощь
        help_menu = menubar.addMenu("Помощь")
        about_action = help_menu.addAction("О программе")
        about_action.triggered.connect(self.show_about)

    def on_region_checkbox_toggled(self, checked):
        """Обработка переключения чекбокса региона"""
        if checked and self.rosunimed_checkbox.isChecked():
            self.rosunimed_checkbox.setChecked(False)

    def on_rosunimed_checkbox_toggled(self, checked):
        """Обработка переключения чекбокса РОСУНИМЕД"""
        if checked and self.region_checkbox.isChecked():
            self.region_checkbox.setChecked(False)

    def check_internet(self):
        """Проверка интернет-соединения"""
        try:
            requests.get("https://www.google.com", timeout=5)
            return True
        except:
            return False

    def load_database(self):
        """Загрузка базы МНН из Excel файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл базы данных ЕСКЛП", "", "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        try:
            xl_file = pd.ExcelFile(file_path)
            smnn_sheet_name = None
            for sheet_name in xl_file.sheet_names:
                if sheet_name.startswith("esklp_smnn"):
                    smnn_sheet_name = sheet_name
                    break
            if not smnn_sheet_name:
                QMessageBox.warning(self, 'Ошибка', 'Лист "esklp_smnn" не найден.')
                return
            df = pd.read_excel(file_path, sheet_name=smnn_sheet_name, header=0)
            mnn_series = df.iloc[:, 0].dropna().unique()
            self.mnn_list = [str(mnn).strip() for mnn in mnn_series if str(mnn).strip()]
            self.mnn_model.setStringList(self.mnn_list)
            self.search_input.setModel(self.mnn_model)
            self.search_input.completer().setModel(self.mnn_model)
            QMessageBox.information(self, 'Успех', f'Загружено {len(self.mnn_list)} МНН.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить: {str(e)}')

    def start_search(self):
        """Запуск поиска ссылок"""
        if not self.check_internet():
            QMessageBox.warning(self, 'Ошибка', 'Нет интернет-соединения')
            return

        search_text = self.search_input.currentText().strip()
        if not search_text:
            QMessageBox.warning(self, 'Ошибка', 'Введите поисковый запрос')
            return

        self.search_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.links_list.clear()
        self.found_links = []

        date_from = self.date_from.date().toString('dd.MM.yyyy')
        date_to = self.date_to.date().toString('dd.MM.yyyy')
        moscow_only = self.region_checkbox.isChecked()
        rosunimed_only = self.rosunimed_checkbox.isChecked()

        try:
            max_contracts = int(self.max_contracts_input.text())
            if max_contracts <= 0:
                raise ValueError()
        except:
            QMessageBox.warning(self, 'Ошибка', 'Введите корректное число')
            self.search_button.setEnabled(True)
            return

        self.thread = LinkFinderWorker(self, search_text, date_from, date_to, moscow_only, rosunimed_only, max_contracts)
        self.thread.update_progress.connect(self.progress_bar.setValue)
        self.thread.update_output.connect(self.on_log_update)
        self.thread.links_found.connect(self.on_link_found)
        self.thread.finished.connect(self.on_search_finished)
        self.thread.start()

        if self.log_dialog is None:
            self.log_dialog = LogDialog(self)
        self.log_dialog.append_log(f"Начат поиск: {search_text}")
        self.append_mini_log(f"Начат поиск: {search_text}")

    def on_link_found(self, link):
        """Обработка найденной ссылки"""
        self.found_links.append(link)
        item = QListWidgetItem(link)
        item.setToolTip(link)
        self.links_list.addItem(item)
        self.total_links_label.setText(f"Всего ссылок: {len(self.found_links)}")

    def on_log_update(self, text):
        """Обновление лога"""
        if self.log_dialog:
            self.log_dialog.append_log(text)
        self.append_mini_log(text)

    def append_mini_log(self, text):
        """Добавление записи в мини-лог"""
        timestamp = time.strftime("%H:%M:%S")
        self.mini_log.append(f"[{timestamp}] {text}")
        self.mini_log.verticalScrollBar().setValue(self.mini_log.verticalScrollBar().maximum())

    def on_search_finished(self, results):
        """Завершение поиска"""
        self.search_button.setEnabled(True)
        self.export_button.setEnabled(bool(results))
        self.copy_button.setEnabled(bool(results))
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Готов (найдено: {len(results)})")
        
        if results:
            QMessageBox.information(self, 'Поиск завершен', f'Найдено {len(results)} ссылок для парсинга.')

    def open_link(self, item):
        """Открытие ссылки в браузере"""
        link = item.text()
        if link.startswith("http"):
            QDesktopServices.openUrl(QUrl(link))

    def export_links(self):
        """Экспорт ссылок в файл"""
        if not self.found_links:
            QMessageBox.warning(self, 'Ошибка', 'Нет ссылок для экспорта')
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить ссылки", "links.txt", "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for link in self.found_links:
                    f.write(link + '\n')
            QMessageBox.information(self, 'Экспорт', f'Ссылки сохранены в файл: {file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить: {str(e)}')

    def copy_all_links(self):
        """Копирование всех ссылок в буфер обмена"""
        if not self.found_links:
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText('\n'.join(self.found_links))
        self.status_label.setText("Ссылки скопированы в буфер обмена")
        QMessageBox.information(self, 'Копирование', f'Скопировано {len(self.found_links)} ссылок в буфер обмена.')

    def clear_links(self):
        """Очистка списка ссылок"""
        if self.found_links:
            reply = QMessageBox.question(
                self, 'Подтверждение', 
                'Вы уверены, что хотите очистить список ссылок?',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.links_list.clear()
                self.found_links = []
                self.total_links_label.setText("Всего ссылок: 0")
                self.export_button.setEnabled(False)
                self.copy_button.setEnabled(False)
                self.status_label.setText("Список очищен")

    def show_log_dialog(self):
        """Показ диалога с полным логом"""
        if self.log_dialog:
            self.log_dialog.show()
            self.log_dialog.raise_()
            self.log_dialog.activateWindow()

    def show_about(self):
        """Показ информации о программе"""
        QMessageBox.about(
            self,
            "О программе",
            "<h2>Поиск ссылок для парсинга ЕИС</h2>"
            "<p>Версия: 1.0</p>"
            "<p>Модуль для поиска ссылок на контракты в ЕИС (zakupki.gov.ru)</p>"
            "<p>Используемые технологии:</p>"
            "<ul>"
            "<li>Python 3.9+</li>"
            "<li>PyQt5</li>"
            "<li>Selenium WebDriver</li>"
            "</ul>"
            "<p>Целевой портал: https://zakupki.gov.ru</p>"
            "<p>Раздел: Поиск контрактов → Результаты поиска</p>"
            "<p>Тип контрактов: только 44-ФЗ</p>"
        )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LinkFinderApp()
    window.show()
    sys.exit(app.exec_())
