import re
import html

# Симуляция разных вариантов
test_cases = [
    "1 10 МГ/МЛ+1 МГ/МЛ",      # с пробелом - правильно
    "110 МГ/МЛ+1 МГ/МЛ",       # без пробела - неправильно, 110 вместо 10
    "1 48 МГ+5 МГ",            # с пробелом
    "148 МГ+5 МГ",             # без пробела - должно быть 48 МГ+5 МГ
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'
dosage_pattern = rf'({single_dose}(?:\s*\+\s*{single_dose})*)'

print("ИСПРАВЛЕННАЯ ЛОГИКА v2 (ищем первое значение с единицей измерения):")
print("=" * 70)

for test in test_cases:
    # Находим все отдельные значения дозировки в тексте
    all_doses = re.findall(single_dose, test, re.IGNORECASE)
    
    if len(all_doses) >= 2:
        # Если найдено 2 или более значений, значит первое число было "слиято" с первым значением
        # Восстанавливаем правильную дозировку, объединяя все найденные значения через +
        result = '+'.join(all_doses)
        print(f"  Найдено значений: {all_doses}")
    elif len(all_doses) == 1:
        result = all_doses[0]
    else:
        result = test
    
    print(f"{repr(test):25} → {result}")
