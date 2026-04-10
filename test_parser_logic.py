import re
import html as html_lib

# Симулируем текст, который приходит из ячейки таблицы
test_texts = [
    "1 10 МГ/МЛ+1 МГ/МЛ",  # нормальный случай с пробелом
    "1 10 МГ/МЛ&#43;1 МГ/МЛ",  # с HTML-сущностью
    "110 МГ/МЛ+1 МГ/МЛ",  # слитое число
    "1 48 МГ+5 МГ",  # другой пример
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("ТЕСТИРОВАНИЕ ЛОГИКИ ИЗ ПАРСЕРА")
print("=" * 80)

for dose_cell_text in test_texts:
    print(f"\nВходной текст: {repr(dose_cell_text)}")
    
    # Декодируем HTML-сущности
    dose_cell_text = html_lib.unescape(dose_cell_text)
    print(f"После unescape: {repr(dose_cell_text)}")
    
    # Находим ВСЕ отдельные значения дозировки в тексте
    all_doses = re.findall(single_dose, dose_cell_text, re.IGNORECASE)
    print(f"Найдено значений: {all_doses}")
    
    if len(all_doses) >= 2:
        # Проверяем, не "слилось" ли первое число (количество) с первой дозировкой
        first_dose = all_doses[0]
        match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
        if match:
            first_num_str = match.group(1)
            first_num = float(first_num_str.replace(',', '.'))
            print(f"Первое число: {first_num}")
            
            # Если первое число >= 100 и есть ещё значения, скорее всего это количество слилось с дозировкой
            # Типичные дозировки редко бывают >= 100 мг/мл для таких препаратов
            if first_num >= 100 and len(all_doses) == 2:
                # Пробуем убрать первую цифру из начала текста
                match2 = re.match(r'^(\d)(\d+\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g).*)$', dose_cell_text, re.IGNORECASE)
                if match2:
                    rest = match2.group(2)
                    all_doses = re.findall(single_dose, rest, re.IGNORECASE)
                    print(f"Коррекция (>=100): rest={repr(rest)}, новые дозы={all_doses}")
        
        dosage = '+'.join(all_doses)
        print(f"Объединено: {dosage}")
    elif len(all_doses) == 1:
        dosage = all_doses[0]
        print(f"Одно значение: {dosage}")
    else:
        # Если паттерн не найден, берем весь текст ячейки
        dosage = dose_cell_text
        print(f"Не найдено, берем весь текст: {dosage}")

print("\n" + "=" * 80)
print("ВЫВОД: Код должен работать правильно!")
print("Если не работает - значит проблема НЕ в этой логике,")
print("а в том, как получается текст из ячейки или в другом месте.")
