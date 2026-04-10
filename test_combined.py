import re
import html

# Проверяем случай "110 МГ/МЛ+1 МГ/МЛ" (без пробела между "1" и "10")
combined = "110 МГ/МЛ+1 МГ/МЛ"
print(f"Текст: {repr(combined)}")

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'
dosage_pattern = rf'({single_dose}(?:\s*\+\s*{single_dose})*)'

matches = re.findall(dosage_pattern, combined, re.IGNORECASE)
print(f"Все совпадения: {matches}")

# А что если паттерн находит несколько отдельных совпадений?
# "110 МГ/МЛ" и "1 МГ/МЛ" по отдельности?
all_matches = re.findall(single_dose, combined, re.IGNORECASE)
print(f"Отдельные значения: {all_matches}")

# Проверяем, что происходит с dosage_with_plus логикой
if matches:
    dosage_with_plus = [m for m in matches if '+' in m]
    print(f"Совпадения с '+': {dosage_with_plus}")
    if dosage_with_plus:
        result = dosage_with_plus[0]
    else:
        result = matches[0]
    print(f"Результат: {result}")
else:
    print("НЕ НАЙДЕНО")
