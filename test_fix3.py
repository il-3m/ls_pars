import re
import html

# Симуляция разных вариантов - включая реальные данные из HTML
test_cases = [
    "1 10 МГ/МЛ+1 МГ/МЛ",      # с пробелом - правильно
    "110 МГ/МЛ+1 МГ/МЛ",       # без пробела - неправильно, 110 вместо 10
    "1 48 МГ+5 МГ",            # с пробелом
    "148 МГ+5 МГ",             # без пробела - должно быть 48 МГ+5 МГ
    "10 МГ/МЛ+1 МГ/МЛ",        # просто дозировка без префикса
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("ИСПРАВЛЕННАЯ ЛОГИКА v3 (ищем паттерн: цифра+пробелы+дозировка):")
print("=" * 70)

for test in test_cases:
    # Новый подход: ищем паттерн где первое число отделено от дозировки
    # Паттерн: начало строки, затем цифры, затем пробелы, затем дозировка (число+единица)
    
    # Ищем все числа в начале, за которыми следует дозировка
    match = re.match(r'^(\d+)\s*((?:\d+\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g).*)$', test, re.IGNORECASE)
    
    if match:
        prefix = match.group(1)
        rest = match.group(2)
        print(f"  Разделено: префикс={prefix}, остальное={repr(rest)}")
        
        # Теперь в rest ищем все значения дозировки
        all_doses = re.findall(single_dose, rest, re.IGNORECASE)
        if len(all_doses) >= 1:
            result = '+'.join(all_doses)
        else:
            result = rest
    else:
        # Обычная логика - ищем все дозировки в тексте
        all_doses = re.findall(single_dose, test, re.IGNORECASE)
        if len(all_doses) >= 1:
            result = '+'.join(all_doses)
        else:
            result = test
    
    print(f"{repr(test):25} → {result}")
