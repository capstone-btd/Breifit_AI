import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from pprint import pprint
from typing import List, Dict, Any

def get_trending_keywords() -> List[Dict[str, Any]]:
    url = "https://trends.google.com/trending?geo=KR&hl=ko&sort=search-volume&status=active&hours=48"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_argument("--log-level=3")
    
    driver = None
    html_source = ""
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        print("Google Trends 페이지에 접속합니다...")
        driver.get(url)

        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody[jsname='cC57zf'] tr[jsname='oKdM2c']")))
        print("페이지 데이터 로딩 완료.")

        html_source = driver.page_source
        
    except Exception as e:
        print(f"Selenium 스크레이핑 중 오류 발생: {e}")
        if driver and driver.page_source:
            print("디버깅을 위해 현재 페이지의 HTML을 'scraping_debug.html' 파일로 저장합니다.")
            with open("scraping_debug.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        return []
    finally:
        if driver:
            driver.quit()

    if not html_source:
        print("오류: 페이지 소스를 가져오지 못했습니다.")
        return []

    soup = BeautifulSoup(html_source, 'lxml')
    
    tbody = soup.find("tbody", attrs={"jsname": "cC57zf"})
    if not tbody:
        print("오류: tbody[jsname='cC57zf'] 요소를 찾을 수 없습니다.")
        print("디버깅을 위해 현재 페이지의 HTML을 'scraping_debug.html' 파일로 저장합니다.")
        with open("scraping_debug.html", "w", encoding="utf-8") as f:
            f.write(html_source)
        return []

    trend_items = tbody.find_all("tr", attrs={"jsname":"oKdM2c"})
    
    if not trend_items:
        print("오류: tbody 내에서 트렌드 행(tr)을 찾을 수 없습니다.")
        print("디버깅을 위해 현재 페이지의 HTML을 'scraping_debug.html' 파일로 저장합니다.")
        with open("scraping_debug.html", "w", encoding="utf-8") as f:
            f.write(tbody.prettify())
        return []

    results = []
    for i, item in enumerate(trend_items):
        keyword_el = item.select_one("div.mZ3RIc")
        search_volume_el = item.select_one("div.qNpYPd")
        
        if keyword_el and search_volume_el:
            keyword = keyword_el.get_text(strip=True).replace(" ", "")
            raw_search_volume = search_volume_el.get_text(strip=True)

            processed_volume = raw_search_volume.replace("검색", "").replace("+회", "").strip()
            
            numeric_volume = 0
            try:
                if "만" in processed_volume:
                    numeric_volume = int(float(processed_volume.replace("만", "")) * 10000)
                elif "천" in processed_volume:
                    numeric_volume = int(float(processed_volume.replace("천", "")) * 1000)
                else:
                    numeric_volume = int(processed_volume)
            except ValueError:
                numeric_volume = 0

            results.append({
                "keyword": keyword,
                "search_volume": numeric_volume
            })
            
    if not results:
        print("오류: tbody 내에서 트렌드 아이템(키워드/검색량)을 찾지 못했습니다.")
        print("디버깅을 위해 현재 페이지의 HTML을 'scraping_debug.html' 파일로 저장합니다.")
        with open("scraping_debug.html", "w", encoding="utf-8") as f:
            f.write(tbody.prettify())

    return results

if __name__ == "__main__":
    trending_keywords = get_trending_keywords()
    
    if trending_keywords:
        print("\n✅ Google Trends 실시간 인기 검색어 (한국)")
        pprint(trending_keywords)
    else:
        print("데이터를 가져오는 데 실패했습니다.")