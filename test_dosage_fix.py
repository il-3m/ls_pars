import re

# Тестируем текущий паттерн
single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

# Разные варианты текста из ячейки
test_cases = [
    "1 10 МГ/МЛ+1 МГ/МЛ",  # Ожидаем: ['10 МГ/МЛ', '1 МГ/МЛ']
    "110 МГ/МЛ+1 МГ/МЛ",   # Ожидаем: ['10 МГ/МЛ', '1 МГ/МЛ'] после коррекции
    "1 48 МГ+5 МГ",        # Ожидаем: ['48 МГ', '5 МГ']
    "48 МГ+5 МГ",          # Ожидаем: ['48 МГ', '5 МГ']
]

for test in test_cases:
    all_doses = re.findall(single_dose, test, re.IGNORECASE)
    print(f"Текст: {repr(test)}")
    print(f"  Найдено: {all_doses}")
    print(f"  Количество: {len(all_doses)}")
    
    if len(all_doses) >= 2:
        first_dose = all_doses[0]
        match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
        if match:
            first_num = float(match.group(1).replace(',', '.'))
            print(f"  Первое число: {first_num}")
            
            # Проверяем гипотезу: если первое значение ТОЛЬКО число (без единицы измерения),
            # то это количество, а не дозировка
            if re.match(r'^\d+$', first_dose.strip()):
                print(f"  -> ПЕРВОЕ ЗНАЧЕНИЕ '{first_dose}' - ЭТО КОЛИЧЕСТВО (нет единицы измерения)!")
                all_doses = all_doses[1:]
                print(f"  -> После удаления: {all_doses}")
    print()
