import re
import html as html_lib

# Тестируем НОВУЮ логику с проверкой маленького первого числа
test_texts = [
    "1 10 МГ/МЛ+1 МГ/МЛ",  # нормальный случай: regular найдет ['10 МГ/МЛ', '1 МГ/МЛ'], first_num=10, не подходит под < 10
    "1 48 МГ+5 МГ",  # normal: ['48 МГ', '5 МГ'], first_num=48
    "2 100 МГ+50 МГ",  # regular найдет ['2 МГ', '100 МГ', '50 МГ'] - 3 значения!
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("ТЕСТИРОВАНИЕ НОВОЙ ЛОГИКИ")
print("=" * 80)

for dose_cell_text in test_texts:
    print(f"\nВходной текст: {repr(dose_cell_text)}")
    
    dose_cell_text = html_lib.unescape(dose_cell_text)
    all_doses = re.findall(single_dose, dose_cell_text, re.IGNORECASE)
    print(f"Найдено значений ({len(all_doses)}): {all_doses}")
    
    if len(all_doses) >= 2:
        first_dose = all_doses[0]
        match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
        if match:
            first_num = float(match.group(1).replace(',', '.'))
            print(f"Первое число из первой дозировки: {first_num}")
            
            if first_num >= 100 and len(all_doses) == 2:
                print(f"-> Сработала коррекция для >= 100")
            elif first_num < 10 and len(all_doses) == 2:
                second_dose = all_doses[1]
                second_match = re.match(r'^(\d+(?:[.,]\d+)?)', second_dose)
                if second_match:
                    second_num = float(second_match.group(1).replace(',', '.'))
                    print(f"Второе число: {second_num}")
                    if second_num > first_num * 5:
                        print(f"-> ПЕРВОЕ ЧИСЛО ({first_num}) < 10 И ВТОРОЕ ({second_num}) > {first_num}*5")
                        print(f"   Убираем первое значение, оставляем: {all_doses[1:]}")
                        all_doses = all_doses[1:]
                    else:
                        print(f"-> Второе число НЕ больше {first_num}*5, оставляем как есть")
        
        dosage = '+'.join(all_doses)
        print(f"Итоговая дозировка: {dosage}")

print("\n" + "=" * 80)
print("ПРОБЛЕМА:")
print("В случае '1 10 МГ/МЛ+1 МГ/МЛ' регулярка находит ['10 МГ/МЛ', '1 МГ/МЛ']")
print("Потому что пробел между '1' и '10' РАЗДЕЛЯЕТ их!")
print("Первое найденное значение - '10 МГ/МЛ', first_num = 10")
print("10 НЕ меньше 10, поэтому новая проверка НЕ срабатывает.")
print()
print("НО! Если бы текст был '110 МГ/МЛ+1 МГ/МЛ' (без пробела),")
print("тогда regular нашла бы ['110 МГ/МЛ', '1 МГ/МЛ'], first_num = 110")
print("И сработала бы коррекция для >= 100.")
print()
print("ВОЗМОЖНО, ПРОБЛЕМА В ТОМ, ЧТО В РЕАЛЬНОМ HTML")
print("текст извлекается БЕЗ пробела между span, т.е. '110 МГ/МЛ+1 МГ/МЛ'?")
