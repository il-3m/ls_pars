import re
import html

# Симуляция того, что возвращает Selenium для разных методов получения текста
test_cases = {
    "cell.text": "1 10 МГ/МЛ+1 МГ/МЛ",  # .text обычно объединяет с пробелом
    "textContent": "1\n                                        10 МГ/МЛ+1 МГ/МЛ\n                                    ",  # textContent сохраняет пробелы и переносы
    "span_join": "1 10 МГ/МЛ+1 МГ/МЛ",  # ручное объединение span
}

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'

print("=" * 80)
print("АНАЛИЗ РАЗНЫХ МЕТОДОВ ПОЛУЧЕНИЯ ТЕКСТА")
print("=" * 80)

for method_name, raw_text in test_cases.items():
    print(f"\n{'='*60}")
    print(f"МЕТОД: {method_name}")
    print(f"Сырой текст: {repr(raw_text)}")
    
    decoded = html.unescape(raw_text)
    normalized = ' '.join(decoded.split())
    print(f"После нормализации: {repr(normalized)}")
    
    all_doses = re.findall(single_dose, normalized, re.IGNORECASE)
    print(f"Найдено дозировок ({len(all_doses)}): {all_doses}")
    
    if len(all_doses) >= 2:
        first_dose = all_doses[0]
        match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
        if match:
            first_num = float(match.group(1).replace(',', '.'))
            print(f"Первое число из первой дозировки: {first_num}")
            
            # Проверка на "слияние" количества с дозировкой
            if first_num < 10 and len(all_doses) == 2:
                second_dose = all_doses[1]
                second_match = re.match(r'^(\d+(?:[.,]\d+)?)', second_dose)
                if second_match:
                    second_num = float(second_match.group(1).replace(',', '.'))
                    print(f"Второе число из второй дозировки: {second_num}")
                    
                    if second_num > first_num * 5:
                        print(f"-> ОБНАРУЖЕНО: первое число ({first_num}) - это количество!")
                        print(f"   Убираем его, оставляем только дозировки: {all_doses[1:]}")
                        all_doses = all_doses[1:]
    
    dosage = '+'.join(all_doses) if all_doses else normalized
    print(f"\nИТОГОВАЯ ДОЗИРОВКА: {repr(dosage)}")

print("\n" + "=" * 80)
print("ВЫВОД:")
print("=" * 80)
print("Проблема в том, что в ячейке есть ДВА span:")
print("  <span>1</span>")
print("  <span>10 МГ/МЛ+1 МГ/МЛ</span>")
print()
print("Если использовать cell.text или textContent, получается:")
print("  '1 10 МГ/МЛ+1 МГ/МЛ'")
print()
print("Регулярка находит:")
print("  ['10 МГ/МЛ', '1 МГ/МЛ']")
print()
print("НО! Если бы текст был '110 МГ/МЛ+1 МГ/МЛ' (без пробела),")
print("тогда регулярка нашла бы ['110 МГ/МЛ', '1 МГ/МЛ'],")
print("и сработала бы коррекция для чисел >= 100.")
print()
print("В данном случае регулярка ПРАВИЛЬНО находит обе дозировки,")
print("потому что пробел между '1' и '10' разделяет их.")
print()
print("ВОЗМОЖНАЯ ПРИЧИНА ПРОБЛЕМЫ В ПАРСЕРЕ:")
print("1. Не декодируются HTML-сущности (&#43; вместо +)")
print("2. Неправильно получается текст из ячейки")
print("3. Регулярка не учитывает какие-то варианты единиц измерения")
