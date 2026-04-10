from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import re
import html

# Создаем простой HTML для теста
html_content = """
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<table>
    <tr>
        <td class="dose-cell">
            <span>1</span>
            <span>10 МГ/МЛ+1 МГ/МЛ</span>
        </td>
    </tr>
</table>
</body>
</html>
"""

chrome_options = Options()
chrome_options.add_argument("--headless")
driver = webdriver.Chrome(options=chrome_options)

try:
    driver.get("data:text/html;charset=utf-8," + html_content.replace('\n', ''))
    time.sleep(1)
    
    cell = driver.find_element(By.CSS_SELECTOR, ".dose-cell")
    
    print("=" * 80)
    print("ТЕСТ ПОЛУЧЕНИЯ ТЕКСТА ИЗ ЯЧЕЙКИ")
    print("=" * 80)
    
    # Метод 1: .text
    text_method = cell.text
    print(f"\n1. cell.text = {repr(text_method)}")
    
    # Метод 2: get_attribute("textContent")
    textcontent = cell.get_attribute("textContent")
    print(f"2. get_attribute('textContent') = {repr(textcontent)}")
    
    # Метод 3: get_attribute("innerHTML")
    innerhtml = cell.get_attribute("innerHTML")
    print(f"3. get_attribute('innerHTML') = {repr(innerhtml)}")
    
    # Метод 4: поиск всех span и объединение
    spans = cell.find_elements(By.TAG_NAME, "span")
    span_texts = [s.text for s in spans]
    print(f"4. [span.text for span in spans] = {span_texts}")
    joined_spans = ' '.join(span_texts)
    print(f"   Объединено: {repr(joined_spans)}")
    
    print("\n" + "=" * 80)
    print("ОБРАБОТКА КАЖДЫМ МЕТОДОМ")
    print("=" * 80)
    
    single_dose = r'\d+(?:[.,]\d+)?\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g)(?:\s*/\s*(?:мг|мл|мкг|г|ед|mg|ml|mcg|g))?'
    
    for i, test_text in enumerate([text_method, textcontent, joined_spans], 1):
        print(f"\n--- Метод {i} ---")
        decoded = html.unescape(test_text)
        normalized = ' '.join(decoded.split())
        print(f"Нормализовано: {repr(normalized)}")
        
        all_doses = re.findall(single_dose, normalized, re.IGNORECASE)
        print(f"Найдено дозировок: {all_doses}")
        
        if len(all_doses) >= 2:
            first_dose = all_doses[0]
            match = re.match(r'^(\d+(?:[.,]\d+)?)', first_dose)
            if match:
                first_num = float(match.group(1).replace(',', '.'))
                print(f"Первое число: {first_num}")
                
                if first_num < 10 and len(all_doses) == 2:
                    second_dose = all_doses[1]
                    second_match = re.match(r'^(\d+(?:[.,]\d+)?)', second_dose)
                    if second_match:
                        second_num = float(second_match.group(1).replace(',', '.'))
                        if second_num > first_num * 5:
                            print(f"-> Убираем первое число ({first_num}), оставляем: {all_doses[1:]}")
                            all_doses = all_doses[1:]
        
        dosage = '+'.join(all_doses)
        print(f"Итог: {repr(dosage)}")

finally:
    driver.quit()
