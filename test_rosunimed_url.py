#!/usr/bin/env python3
"""
Тестовый скрипт для проверки URL поиска по Росунимеду.
Запускается через Selenium и проверяет, что фильтр работает корректно.
"""

import sys
import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_rosunimed_search():
    """Проверка поиска по Росунимеду"""
    
    base_url = "https://zakupki.gov.ru/epz/contract/search/results.html"
    params = {
        "searchString": "пропофол",
        "morphology": "on",
        "fz44": "on",
        "contractStageList": "1",
        "contractStageList_1": "on",
        "contractDateFrom": "01.01.2024",
        "contractDateTo": "31.12.2025",
        "sortBy": "UPDATE_DATE",
        "pageNumber": "1",
        "sortDirection": "false",
        "recordsPerPage": "_10",
        "strictEqual": "true",
        "customerIdOrg": "14269::zZ03731000459zZzZzZzZ",
        "customerName": "РОССИЙСКИЙ УНИВЕРСИТЕТ МЕДИЦИНЫ"
    }
    
    url = base_url + "?" + urllib.parse.urlencode(params, safe='', quote_via=urllib.parse.quote)
    print(f"URL для тестирования:\n{url}\n")
    
    # Инициализация WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        print("Загрузка страницы...")
        driver.get(url)
        time.sleep(5)
        
        # Проверка на CAPTCHA
        if "captcha" in driver.page_source.lower():
            print("⚠️  Обнаружена CAPTCHA!")
            return False
        
        # Получаем информацию о найденных контрактах
        try:
            results_count = driver.find_element(By.CSS_SELECTOR, ".data-count span")
            print(f"Найдено результатов: {results_count.text}")
        except:
            print("Не удалось определить количество результатов")
        
        # Проверяем заказчиков в результатах
        customers = driver.find_elements(By.CSS_SELECTOR, ".customer-name, .organization-name, [data-test='customer-info']")
        print(f"\nНайдено элементов с заказчиками: {len(customers)}")
        
        for i, customer in enumerate(customers[:5], 1):
            name = customer.text.strip()
            is_rosunimed = "РОССИЙСКИЙ УНИВЕРСИТЕТ МЕДИЦИНЫ" in name or "Росунимед" in name
            marker = "✓" if is_rosunimed else "✗"
            print(f"  {marker} Заказчик {i}: {name[:100]}...")
        
        # Проверяем URL в адресной строке
        current_url = driver.current_url
        print(f"\nТекущий URL после загрузки:")
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(current_url).query)
        if 'customerIdOrg' in parsed:
            decoded = urllib.parse.unquote(parsed['customerIdOrg'][0])
            print(f"  customerIdOrg: {decoded}")
        if 'customerName' in parsed:
            decoded = urllib.parse.unquote(parsed['customerName'][0])
            print(f"  customerName: {decoded}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_rosunimed_search()
    sys.exit(0 if success else 1)
