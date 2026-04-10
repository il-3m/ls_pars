import re

# Тестирование исправленного кода
test_cases = [
    ('1 10 МГ/МЛ+1 МГ/МЛ', '10 МГ/МЛ+1 МГ/МЛ'),      # с пробелом - должно быть '10 МГ/МЛ+1 МГ/МЛ'
    ('110 МГ/МЛ+1 МГ/МЛ', '10 МГ/МЛ+1 МГ/МЛ'),       # без пробела - должно быть '10 МГ/МЛ+1 МГ/МЛ' (исправляем!)
    ('1 48 МГ+5 МГ', '48 МГ+5 МГ'),                  # с пробелом - должно быть '48 МГ+5 МГ'
    ('148 МГ+5 МГ', '48 МГ+5 МГ'),                   # без пробела - должно быть '48 МГ+5 МГ' (исправляем!)
    ('10 МГ/МЛ+1 МГ/МЛ', '10 МГ/МЛ+1 МГ/МЛ'),        # просто дозировка - должно быть '10 МГ/МЛ+1 МГ/МЛ'
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print('ТЕСТИРОВАНИЕ ИСПРАВЛЕННОГО КОДА:')
print('=' * 70)

all_pass = True
for test_input, expected in test_cases:
    all_doses = re.findall(single_dose, test_input, re.IGNORECASE)
    
    if len(all_doses) >= 2:
        dosage = '+'.join(all_doses)
    elif len(all_doses) == 1:
        dosage = all_doses[0]
    else:
        dosage = test_input
    
    status = 'PASS' if dosage == expected else 'FAIL'
    if status == 'FAIL':
        all_pass = False
    print(f'{status}: {repr(test_input):25} -> {dosage} (ожид: {expected})')

print('=' * 70)
print('ВСЕ ТЕСТЫ ПРОЙДЕНЫ!' if all_pass else 'ЕСТЬ ОШИБКИ!')
