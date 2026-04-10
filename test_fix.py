import re
import html

# Симуляция разных вариантов
test_cases = [
    "1 10 МГ/МЛ+1 МГ/МЛ",      # с пробелом - правильно
    "110 МГ/МЛ+1 МГ/МЛ",       # без пробела - неправильно, 110 вместо 10
    "1 48 МГ+5 МГ",            # с пробелом
    "148 МГ+5 МГ",             # без пробела
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'
dosage_pattern = rf'({single_dose}(?:\s*\+\s*{single_dose})*)'

print("ТЕКУЩАЯ ЛОГИКА:")
print("=" * 70)
for test in test_cases:
    matches = re.findall(dosage_pattern, test, re.IGNORECASE)
    if matches:
        dosage_with_plus = [m for m in matches if '+' in m]
        result = dosage_with_plus[0] if dosage_with_plus else matches[0]
    else:
        result = test
    print(f"{repr(test):25} → {result}")

print()
print("ИСПРАВЛЕННАЯ ЛОГИКА (убираем первое число, если оно без единицы измерения):")
print("=" * 70)

for test in test_cases:
    # Сначала находим все отдельные значения дозировки
    all_doses = re.findall(single_dose, test, re.IGNORECASE)
    
    # Если есть несколько значений через +, пробуем восстановить правильную дозировку
    # Ищем паттерн: число в начале без единицы измерения + дозировка с +
    
    # Новый подход: ищем дозировку, игнорируя первое число, если за ним сразу идет другая дозировка
    # Паттерн: опциональное число в начале (которое может быть количеством), затем основная дозировка
    
    # Вариант 1: убираем первое число, если оно не имеет единицы измерения и за ним следует дозировка
    match = re.match(r'^(\d+)\s*([1-9]\d*\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g).*)$', test, re.IGNORECASE)
    if match:
        prefix_num = match.group(1)
        rest = match.group(2)
        print(f"  Найдено разделение: количество={prefix_num}, остальное={repr(rest)}")
        
        # Теперь ищем дозировку в rest
        matches = re.findall(dosage_pattern, rest, re.IGNORECASE)
        if matches:
            dosage_with_plus = [m for m in matches if '+' in m]
            result = dosage_with_plus[0] if dosage_with_plus else matches[0]
        else:
            result = rest
    else:
        # Обычная логика
        matches = re.findall(dosage_pattern, test, re.IGNORECASE)
        if matches:
            dosage_with_plus = [m for m in matches if '+' in m]
            result = dosage_with_plus[0] if dosage_with_plus else matches[0]
        else:
            result = test
    
    print(f"{repr(test):25} → {result}")
