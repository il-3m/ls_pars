#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой лаунчер для парсера лекарств ЕИС.
Запускает eis_parser.py с выбранными параметрами через GUI.
"""

import sys
import subprocess
from pathlib import Path

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QCheckBox, QDateEdit,
        QMessageBox, QGroupBox, QFormLayout, QSpinBox, QStatusBar,
        QTextEdit, QFileDialog, QProgressBar
    )
    from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
    from PyQt5.QtGui import QFont
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False


class ParserWorker(QThread):
    """Рабочий поток для запуска парсера"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    
    def __init__(self, args):
        super().__init__()
        self.args = args
        
    def run(self):
        try:
            script_path = Path(__file__).parent / "eis_parser.py"
            cmd = [sys.executable, str(script_path)] + self.args
            
            self.output_signal.emit(f"Запуск: {' '.join(cmd)}\n")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            for line in process.stdout:
                self.output_signal.emit(line)
                
            process.wait()
            
            if process.returncode == 0:
                self.output_signal.emit("\n✅ Парсинг завершён успешно!\n")
                self.finished_signal.emit(True)
            else:
                self.output_signal.emit(f"\n❌ Ошибка парсинга (код {process.returncode})\n")
                self.finished_signal.emit(False)
                
        except Exception as e:
            self.output_signal.emit(f"\n❌ Критическая ошибка: {str(e)}\n")
            self.finished_signal.emit(False)


class SimpleLauncher(QMainWindow):
    """Простое окно запуска парсера"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("🔍 Парсер лекарств ЕИС - Запуск")
        self.setMinimumWidth(500)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Заголовок
        title = QLabel("⚕️ Парсер лекарственных средств")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Автоматический поиск и парсинг контрактов на zakupki.gov.ru")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # Группа параметров поиска
        search_group = QGroupBox("📋 Параметры поиска")
        search_layout = QFormLayout()
        search_layout.setSpacing(10)
        
        # Поисковый запрос (МНН)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Например: АЗИТРОМИЦИН, ПАРАЦЕТАМОЛ")
        self.search_input.setMinimumHeight(30)
        search_layout.addRow("Поисковый запрос (МНН):", self.search_input)
        
        # Даты
        date_layout = QHBoxLayout()
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        
        date_layout.addWidget(self.date_from)
        date_layout.addWidget(QLabel(" — "))
        date_layout.addWidget(self.date_to)
        search_layout.addRow("Период поиска:", date_layout)
        
        # Максимум контрактов
        self.max_contracts = QSpinBox()
        self.max_contracts.setRange(1, 1000)
        self.max_contracts.setValue(20)
        self.max_contracts.setMinimumHeight(30)
        search_layout.addRow("Макс. контрактов:", self.max_contracts)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Группа фильтров
        filter_group = QGroupBox("🎯 Фильтры (опционально)")
        filter_layout = QVBoxLayout()
        
        self.moscow_only = QCheckBox("Искать только в Москве и Московской области")
        self.rosunimed_only = QCheckBox("Искать только в РОСУНИМЕД")
        
        # Взаимное исключение
        self.moscow_only.toggled.connect(lambda: self._toggle_exclusive(self.moscow_only, self.rosunimed_only))
        self.rosunimed_only.toggled.connect(lambda: self._toggle_exclusive(self.rosunimed_only, self.moscow_only))
        
        filter_layout.addWidget(self.moscow_only)
        filter_layout.addWidget(self.rosunimed_only)
        filter_layout.addStretch()
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # Кнопки управления
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Запустить парсинг")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_btn.clicked.connect(self.start_parsing)
        
        self.stop_btn = QPushButton("⏹️ Остановить")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_parsing)
        self.stop_btn.setEnabled(False)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        # Прогресс бар
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate mode
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Лог вывода
        log_group = QGroupBox("📝 Журнал выполнения")
        log_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMinimumHeight(200)
        log_layout.addWidget(self.log_output)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Статус бар
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов к работе")
        
        # Инструкция
        help_text = QLabel(
            "💡 <b>Как использовать:</b><br>"
            "1. Введите название лекарства (МНН)<br>"
            "2. Выберите период поиска (по умолчанию - последние 3 месяца)<br>"
            "3. Укажите максимальное количество контрактов<br>"
            "4. При необходимости включите фильтры по региону или заказчику<br>"
            "5. Нажмите «Запустить парсинг»<br><br>"
            "Результаты будут сохранены в папке <b>export/</b>"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(help_text)
        
    def _toggle_exclusive(self, checked_box, other_box):
        """Обеспечивает взаимное исключение чекбоксов"""
        if checked_box.isChecked():
            other_box.setChecked(False)
    
    def start_parsing(self):
        """Запуск парсера"""
        search_text = self.search_input.text().strip()
        
        if not search_text:
            QMessageBox.warning(self, "Ошибка", "Введите поисковый запрос (МНН)")
            return
        
        # Формирование аргументов
        args = ["--search", search_text]
        
        # Даты
        date_from = self.date_from.date().toString("dd.MM.yyyy")
        date_to = self.date_to.date().toString("dd.MM.yyyy")
        args.extend(["--date-from", date_from])
        args.extend(["--date-to", date_to])
        
        # Максимум контрактов
        args.extend(["--max-contracts", str(self.max_contracts.value())])
        
        # Фильтры
        if self.moscow_only.isChecked():
            args.append("--moscow-only")
        if self.rosunimed_only.isChecked():
            args.append("--rosunimed-only")
        
        # Блокировка интерфейса
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.statusBar.showMessage("Выполняется парсинг...")
        
        # Очистка лога
        self.log_output.clear()
        self.log_output.append(f"🚀 Запуск парсинга: {search_text}")
        self.log_output.append(f"📅 Период: {date_from} - {date_to}")
        self.log_output.append(f"📊 Макс. контрактов: {self.max_contracts.value()}")
        if self.moscow_only.isChecked():
            self.log_output.append("📍 Фильтр: Москва и МО")
        if self.rosunimed_only.isChecked():
            self.log_output.append("🏥 Фильтр: РОСУНИМЕД")
        self.log_output.append("-" * 50)
        
        # Запуск рабочего потока
        self.worker = ParserWorker(args)
        self.worker.output_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.parsing_finished)
        self.worker.start()
        
    def stop_parsing(self):
        """Остановка парсера"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Подтверждение",
                "Вы уверены, что хотите остановить парсинг?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.terminate()
                self.append_log("\n⏹️ Парсинг остановлен пользователем")
                self.parsing_finished(False)
    
    def append_log(self, text):
        """Добавление текста в лог"""
        self.log_output.append(text.rstrip())
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )
    
    def parsing_finished(self, success):
        """Завершение парсинга"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
        
        if success:
            self.statusBar.showMessage("✅ Парсинг завершён успешно!")
            QMessageBox.information(
                self, "Готово",
                "Парсинг завершён успешно!\n\n"
                "Результаты сохранены в папке export/\n"
                "Файлы: result.csv и result.xlsx"
            )
        else:
            self.statusBar.showMessage("❌ Парсинг завершён с ошибкой")
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Подтверждение",
                "Парсинг ещё выполняется. Закрыть программу?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    if not PYQT5_AVAILABLE:
        print("❌ Ошибка: PyQt5 не установлен.")
        print("Установите командой: pip install PyQt5")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = SimpleLauncher()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
