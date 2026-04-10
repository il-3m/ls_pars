import re

# Тестирование исправленного кода - с дополнительной логикой
test_cases = [
    ('1 10 МГ/МЛ+1 МГ/МЛ', '10 МГ/МЛ+1 МГ/МЛ'),      # с пробелом - должно быть '10 МГ/МЛ+1 МГ/МЛ'
    ('110 МГ/МЛ+1 МГ/МЛ', '10 МГ/МЛ+1 МГ/МЛ'),       # без пробела - должно быть '10 МГ/МЛ+1 МГ/МЛ' (исправляем!)
    ('1 48 МГ+5 МГ', '48 МГ+5 МГ'),                  # с пробелом - должно быть '48 МГ+5 МГ'
    ('148 МГ+5 МГ', '48 МГ+5 МГ'),                   # без пробела - должно быть '48 МГ+5 МГ' (исправляем!)
    ('10 МГ/МЛ+1 МГ/МЛ', '10 МГ/МЛ+1 МГ/МЛ'),        # просто дозировка - должно быть '10 МГ/МЛ+1 МГ/МЛ'
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print('ТЕСТИРОВАНИЕ ИСПРАВЛЕННОГО КОДА v2:')
print('=' * 70)

all_pass = True
for test_input, expected in test_cases:
    all_doses = re.findall(single_dose, test_input, re.IGNORECASE)
    
    if len(all_doses) >= 2:
        # Проверяем, не "слилось" ли первое число с первой дозировкой
        first_dose = all_doses[0]
        # Извлекаем число из первой дозировки
        match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
        if match:
            first_num_str = match.group(1)
            first_num = float(first_num_str.replace(',', '.'))
            
            # Если первое число >= 100 и есть ещё значения, скорее всего это количество слилось с дозировкой
            # Типичные дозировки редко бывают >= 100 мг/мл для таких препаратов
            if first_num >= 100 and len(all_doses) == 2:
                # Пробуем убрать первую цифру
                match2 = re.match(r'^(\d)(\d+\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g).*)$', test_input, re.IGNORECASE)
                if match2:
                    prefix = match2.group(1)
                    rest = match2.group(2)
                    all_doses = re.findall(single_dose, rest, re.IGNORECASE)
                    print(f'  Коррекция: префикс={prefix}, rest={repr(rest)}, новые дозы={all_doses}')
        
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
