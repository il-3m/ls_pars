#!/usr/bin/env python3
"""Тестовый скрипт для проверки структуры unified_parser.py"""

import sys
sys.path.insert(0, '/workspace')

# Проверяем импорты
try:
    from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidget
    print("✓ PyQt5 импортирован")
except Exception as e:
    print(f"✗ Ошибка импорта PyQt5: {e}")
    sys.exit(1)

# Проверяем eis_parser
try:
    from eis_parser import FIELD_ORDER, EXPORT_HEADERS_RU
    print(f"✓ eis_parser импортирован (полей: {len(FIELD_ORDER)})")
except Exception as e:
    print(f"✗ Ошибка импорта eis_parser: {e}")
    sys.exit(1)

# Проверяем синтаксис unified_parser
try:
    import py_compile
    py_compile.compile('/workspace/unified_parser.py', doraise=True)
    print("✓ unified_parser.py - синтаксис корректен")
except Exception as e:
    print(f"✗ Ошибка синтаксиса: {e}")
    sys.exit(1)

print("\n=== Все проверки пройдены ===")
print(f"Таблица будет иметь {len(FIELD_ORDER)} колонок:")
for i, field in enumerate(FIELD_ORDER[:5]):
    print(f"  {i+1}. {field}: {EXPORT_HEADERS_RU[field]}")
if len(FIELD_ORDER) > 5:
    print(f"  ... и еще {len(FIELD_ORDER) - 5} колонок")
