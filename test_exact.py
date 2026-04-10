import re

# Точная симуляция того, что происходит в парсере
test_texts = [
    "1 10 МГ/МЛ+1 МГ/МЛ",  # textContent с пробелом между span
    "110 МГ/МЛ+1 МГ/МЛ",   # без пробела
    " 1  10 МГ/МЛ+1 МГ/МЛ ",  # с лишними пробелами
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("=== ТЕСТИРОВАНИЕ ПАТТЕРНА ===\n")

for dose_cell_text in test_texts:
    print(f"Входной текст: {repr(dose_cell_text)}")
    
    # Нормализация пробелов (как в коде)
    normalized = ' '.join(dose_cell_text.split())
    print(f"После нормализации: {repr(normalized)}")
    
    # Поиск всех дозировок
    all_doses = re.findall(single_dose, normalized, re.IGNORECASE)
    print(f"Найдено дозировок: {all_doses}")
    print(f"Количество: {len(all_doses)}")
    
    if len(all_doses) >= 1:
        if len(all_doses) >= 2:
            first_val = all_doses[0].strip()
            print(f"Первое значение: {repr(first_val)}")
            
            # Проверка на чистое число
            if re.match(r'^\d+(?:[.,]\d+)?$', first_val):
                print(f"  -> Это чистое число, убираем")
                all_doses = all_doses[1:]
            else:
                # Проверка: первое число < 10, второе значительно больше
                first_match = re.match(r'^(\d+(?:[.,]\d+)?)', all_doses[0])
                second_match = re.match(r'^(\d+(?:[.,]\d+)?)', all_doses[1])
                if first_match and second_match:
                    first_num = float(first_match.group(1).replace(',', '.'))
                    second_num = float(second_match.group(1).replace(',', '.'))
                    print(f"  -> Первое число: {first_num}, второе: {second_num}")
                    if first_num < 10 and second_num > first_num * 5:
                        print(f"  -> Первое число - количество, убираем")
                        all_doses = all_doses[1:]
        
        dosage = '+'.join(all_doses)
        print(f"ИТОГОВАЯ ДОЗИРОВКА: {dosage}")
    else:
        print(f"ИТОГОВАЯ ДОЗИРОВКА: {dose_cell_text} (паттерн не найден)")
    
    print()
