from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# HTML с точной структурой как на сайте
html_content = """
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<table class="tableBlock">
    <tbody>
        <tr class="tableBlock__row">
            <td class="tableBlock__col">МАГНЕ B6</td>
            <td class="tableBlock__col">ЛП-№(004011)-(РГ-RU)</td>
            <td class="tableBlock__col">РАСТВОР ДЛЯ ПРИЕМА ВНУТРЬ</td>
            <td class="tableBlock__col">
                <span>1</span>
                <span>10 МГ/МЛ+1 МГ/МЛ</span>
            </td>
            <td class="tableBlock__col"></td>
        </tr>
    </tbody>
</table>
</body>
</html>
"""

# Создаем драйвер
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=options)

try:
    # Загружаем HTML
    driver.get('data:text/html,' + html_content)
    time.sleep(1)
    
    # Находим ячейку дозировки (4-я колонка, индекс 3)
    cells = driver.find_elements(By.CSS_SELECTOR, "td.tableBlock__col")
    dose_cell = cells[3]  # 4-я ячейка (0-based index)
    
    print("=== РЕЗУЛЬТАТЫ ИЗВЛЕЧЕНИЯ ТЕКСТА ===\n")
    
    # Метод 1: .text
    text_method = dose_cell.text
    print(f"1. dose_cell.text = {repr(text_method)}")
    
    # Метод 2: get_attribute("textContent")
    textcontent = dose_cell.get_attribute("textContent")
    print(f"2. get_attribute('textContent') = {repr(textcontent)}")
    
    # Метод 3: get_attribute("innerText")
    innertext = dose_cell.get_attribute("innerText")
    print(f"3. get_attribute('innerText') = {repr(innertext)}")
    
    # Метод 4: Обход всех текстовых узлов через JavaScript
    text_nodes = driver.execute_script("""
        var element = arguments[0];
        var texts = [];
        var walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
        while(walker.nextNode()) {
            var txt = walker.currentNode.nodeValue.trim();
            if(txt) texts.push(txt);
        }
        return texts;
    """, dose_cell)
    print(f"4. Текстовые узлы (JS): {text_nodes}")
    print(f"   Объединено: {repr(' '.join(text_nodes))}")
    
    # Метод 5: Получение текста из каждого span отдельно
    spans = dose_cell.find_elements(By.TAG_NAME, "span")
    span_texts = [s.text for s in spans]
    print(f"5. Текст из span: {span_texts}")
    print(f"   Объединено: {repr(' '.join(span_texts))}")
    
finally:
    driver.quit()
