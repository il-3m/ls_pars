import re
import html

# Симуляция того, что может приходить из Selenium get_attribute("textContent")
# с разными вариантами форматирования

test_cases = [
    # Вариант 1: нормальный, с двумя span
    '1 10 МГ/МЛ+1 МГ/МЛ',
    
    # Вариант 2: с переносом строки между span
    '1\n10 МГ/МЛ+1 МГ/МЛ',
    
    # Вариант 3: с табуляцией
    '1\t10 МГ/МЛ+1 МГ/МЛ',
    
    # Вариант 4: несколько пробелов
    '1   10 МГ/МЛ+1 МГ/МЛ',
    
    # Вариант 5: HTML-сущность плюса
    '1 10 МГ/МЛ&#43;1 МГ/МЛ',
    
    # Вариант 6: плюс тоже как сущность
    '1 10 МГ/МЛ&#43;1 МГ/МЛ',
    
    # Вариант 7: что если текст разбит на части
    '1 10 МГ/МЛ +1 МГ/МЛ',
    
    # Вариант 8: что если после первого значения есть пробел перед плюсом
    '1 10 МГ/МЛ + 1 МГ/МЛ',
]

single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'
dosage_pattern = rf'({single_dose}(?:\s*\+\s*{single_dose})*)'

print('Тестирование паттерна дозировки:')
print('=' * 70)

for i, test in enumerate(test_cases, 1):
    # Нормализация пробелов (как в коде парсера)
    normalized = ' '.join(test.split())
    # Декодируем HTML-сущности
    decoded = html.unescape(normalized)
    
    print(f'Тест {i}:')
    print(f'  Исходный: {repr(test)}')
    print(f'  После norm: {repr(normalized)}')
    print(f'  После unescape: {repr(decoded)}')
    
    matches = re.findall(dosage_pattern, decoded, re.IGNORECASE)
    print(f'  Совпадения: {matches}')
    
    if matches:
        dosage_with_plus = [m for m in matches if '+' in m]
        if dosage_with_plus:
            result = dosage_with_plus[0]
        else:
            result = matches[0]
        print(f'  → Результат: {result}')
    else:
        print('  → Результат: НЕ НАЙДЕНО (будет взят весь текст)')
    print()
