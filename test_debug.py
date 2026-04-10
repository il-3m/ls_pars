import re
import html

# Тестовые данные из HTML
test_cases = [
    "1 10 МГ/МЛ+1 МГ/МЛ",  # нормальный случай
    "1 10 МГ/МЛ&#43;1 МГ/МЛ",  # с HTML-сущностью
    "1 10 МГ/МЛ+1 МГ/МЛ",  # после unescape
    "110 МГ/МЛ+1 МГ/МЛ",  # слитое число
    "1 48 МГ+5 МГ",  # другой пример
    "48 МГ+5 МГ",  # без количества
]

# Паттерн для одного значения дозировки
single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("=" * 80)
for i, test in enumerate(test_cases, 1):
    print(f"\nТест {i}: {repr(test)}")
    
    # Декодируем HTML-сущности
    decoded = html.unescape(test)
    print(f"  После unescape: {repr(decoded)}")
    
    # Нормализуем пробелы
    normalized = ' '.join(decoded.split())
    print(f"  После нормализации: {repr(normalized)}")
    
    # Находим все дозировки
    all_doses = re.findall(single_dose, normalized, re.IGNORECASE)
    print(f"  Найдено дозировок: {all_doses}")
    
    if len(all_doses) >= 2:
        first_dose = all_doses[0]
        match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
        if match:
            first_num = float(match.group(1).replace(',', '.'))
            print(f"  Первое число: {first_num}")
            
            if first_num >= 100 and len(all_doses) == 2:
                print(f"  -> Применяем коррекцию (число >= 100)")
                match2 = re.match(r'^(\d)(\d+\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g).*)$', normalized, re.IGNORECASE)
                if match2:
                    rest = match2.group(2)
                    all_doses = re.findall(single_dose, rest, re.IGNORECASE)
                    print(f"  После коррекции: {all_doses}")
            elif first_num < 10:
                # Проверяем, не является ли первое число отдельным количеством
                # Если первое значение - просто маленькое число (1-9), а второе начинается с большего числа
                second_dose = all_doses[1]
                second_match = re.match(r'^(\d+(?:[.,]\d+)?)', second_dose)
                if second_match:
                    second_num = float(second_match.group(1).replace(',', '.'))
                    if second_num > first_num * 5:  # Второе число значительно больше первого
                        print(f"  -> Первое число ({first_num}) скорее всего количество, убираем его")
                        all_doses = all_doses[1:]
    
    dosage = '+'.join(all_doses)
    print(f"  Итоговая дозировка: {repr(dosage)}")
