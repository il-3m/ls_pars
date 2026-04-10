import re
import html

# Тестируем разные варианты текста из ячейки дозировки
test_cases = [
    "1 10 МГ/МЛ+1 МГ/МЛ",      # С пробелом между span
    "110 МГ/МЛ+1 МГ/МЛ",       # Без пробела (слитно)
    "1 48 МГ+5 МГ",            # Таблетки с пробелом
    "148 МГ+5 МГ",             # Таблетки без пробела
    "10 МГ/МЛ+1 МГ/МЛ",        # Только дозировка (без количества)
]

# Паттерн для одного значения дозировки
single_dose = r'(\d+(?:[.,]\d+)?)\s*(мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("=== ТЕСТИРОВАНИЕ ПАРСИНГА ДОЗИРОВКИ ===\n")

for dose_cell_text in test_cases:
    print(f"Входной текст: {repr(dose_cell_text)}")
    
    # Декодируем HTML-сущности
    dose_cell_text = html.unescape(dose_cell_text)
    
    # Разбиваем слипшиеся цифры в начале строки
    if re.match(r'^[1-9]\d', dose_cell_text):
        dose_cell_text = re.sub(r'^([1-9])(\d)', r'\1 \2', dose_cell_text)
        print(f"После разбивки: {repr(dose_cell_text)}")
    
    # Находим все совпадения
    all_matches = re.findall(single_dose, dose_cell_text, re.IGNORECASE)
    print(f"Найдено совпадений: {all_matches}")
    
    if all_matches:
        doses = []
        for i, match in enumerate(all_matches):
            num_str = match[0]
            unit1 = match[1]
            unit2 = match[2] if len(match) > 2 and match[2] else ''
            num_val = float(num_str.replace(',', '.'))
            
            print(f"  [{i}] Число: {num_str}, Ед1: {unit1}, Ед2: {unit2}, Значение: {num_val}")
            
            # Случай 1: число >= 100
            if i == 0 and num_val >= 100 and len(num_str) >= 3:
                rest_digits = num_str[1:]
                dose_str = f"{rest_digits} {unit1}" + (f"/{unit2}" if unit2 else "")
                print(f"      -> Коррекция >=100: {dose_str}")
                doses.append(dose_str)
            # Случай 2: первое число маленькое (1-9)
            elif i == 0 and num_val < 10 and len(all_matches) > 1:
                next_num_str = all_matches[1][0]
                next_num_val = float(next_num_str.replace(',', '.'))
                if next_num_val > num_val * 5:
                    print(f"      -> Пропускаем количество {num_str}")
                else:
                    dose_str = f"{num_str} {unit1}" + (f"/{unit2}" if unit2 else "")
                    doses.append(dose_str)
                    print(f"      -> Добавляем: {dose_str}")
            # Случай 3: все остальные
            else:
                dose_str = f"{num_str} {unit1}" + (f"/{unit2}" if unit2 else "")
                doses.append(dose_str)
                print(f"      -> Добавляем: {dose_str}")
        
        dosage = '+'.join(doses)
        print(f"ИТОГОВАЯ ДОЗИРОВКА: {dosage}\n")
    else:
        print(f"ИТОГОВАЯ ДОЗИРОВКА: {dose_cell_text}\n")
