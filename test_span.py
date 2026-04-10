import re
import html

# Что если каждый span обрабатывается отдельно?
# Первый span: "1"
# Второй span: "10 МГ/МЛ+1 МГ/МЛ"

# Симуляция того, что может происходить в коде:
# cell_texts собирается из textContent каждого td
# но что если внутри td есть несколько span и они читаются отдельно?

span1 = "1"
span2 = "10 МГ/МЛ+1 МГ/МЛ"

# Если код читает каждый span отдельно и concat'ит их:
combined = span1 + span2  # "110 МГ/МЛ+1 МГ/МЛ" - без пробела!
print(f"Без пробела: {repr(combined)}")

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'
dosage_pattern = rf'({single_dose}(?:\s*\+\s*{single_dose})*)'

matches = re.findall(dosage_pattern, combined, re.IGNORECASE)
print(f"Совпадения: {matches}")

if matches:
    dosage_with_plus = [m for m in matches if '+' in m]
    if dosage_with_plus:
        result = dosage_with_plus[0]
    else:
        result = matches[0]
    print(f"Результат: {result}")
else:
    print("НЕ НАЙДЕНО")

print()

# А если с пробелом между span?
combined2 = span1 + " " + span2  # "1 10 МГ/МЛ+1 МГ/МЛ"
print(f"С пробелом: {repr(combined2)}")
matches2 = re.findall(dosage_pattern, combined2, re.IGNORECASE)
print(f"Совпадения: {matches2}")

if matches2:
    dosage_with_plus = [m for m in matches2 if '+' in m]
    if dosage_with_plus:
        result = dosage_with_plus[0]
    else:
        result = matches2[0]
    print(f"Результат: {result}")
else:
    print("НЕ НАЙДЕНО")
