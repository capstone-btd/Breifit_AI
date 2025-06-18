from playwright.async_api import Browser, Page
from bs4 import BeautifulSoup
from pprint import pprint
from typing import List, Dict, Any
import os
import asyncio

async def get_trending_keywords(browser: Browser) -> List[Dict[str, Any]]:
    print("\n[trends] 공유된 브라우저를 사용하여 스크레이핑 시작 (Async)...")
    html_source = ""
    page: Page = None

    try:
        print("[trends] 1. 새 페이지를 엽니다.")
        page = await browser.new_page()
        
        url = "https://trends.google.com/trending?geo=KR&hl=ko&sort=search-volume&status=active&hours=48"
        print(f"[trends] 2. Google Trends URL로 이동합니다: {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

        print("[trends] 3. 쿠키 동의 팝업이 있는지 확인하고 처리합니다.")
        cookie_button_selector = "button[aria-label='모두 동의']"
        try:
            await page.wait_for_selector(cookie_button_selector, timeout=5000)
            print("[trends]    - '모두 동의' 버튼을 발견하여 클릭합니다.")
            await page.click(cookie_button_selector)
            await page.wait_for_load_state('domcontentloaded', timeout=5000)
            print("[trends]    - 쿠키 팝업 처리가 완료되었습니다.")
        except Exception:
            print("[trends]    - 쿠키 동의 팝업이 없거나 이미 처리되었습니다. 계속 진행합니다.")

        print("[trends] 4. 실제 데이터가 로드되기를 기다립니다.")
        target_selector = "tbody[jsname='cC57zf'] tr[jsname='oKdM2c']"
        await page.wait_for_selector(target_selector, timeout=20000)
        print("[trends] 5. 데이터 로딩을 확인했습니다.")

        html_source = await page.content()
        print("[trends] 6. 페이지의 HTML 컨텐츠를 성공적으로 가져왔습니다.")

    except Exception as e:
        print(f"\n!!! [trends] Playwright 스크레이핑 중 예외 발생: {e} !!!\n")
        if page:
            screenshot_path = "playwright_error_screenshot.png"
            try:
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"오류 발생 시점의 스크린샷을 현재 폴더에 '{os.path.abspath(screenshot_path)}' 파일로 저장했습니다.")
            except Exception as se:
                print(f"스크린샷 저장 중 별도의 오류 발생: {se}")
        return []
    finally:
        if page:
            await page.close()
            print("[trends] 7. 사용한 페이지를 닫았습니다. (브라우저는 계속 실행 중)")

    if not html_source:
        print("[trends] 오류: 페이지 소스를 가져오지 못했습니다.")
        return []
    
    soup = BeautifulSoup(html_source, 'lxml')
    
    tbody = soup.find("tbody", attrs={"jsname": "cC57zf"})
    if not tbody:
        print("[trends] 오류: tbody[jsname='cC57zf'] 요소를 찾을 수 없습니다.")
        return []

    trend_items = tbody.find_all("tr", attrs={"jsname":"oKdM2c"})
    
    if not trend_items:
        print("[trends] 오류: tbody 내에서 트렌드 행(tr)을 찾을 수 없습니다.")
        return []

    results = []
    for item in trend_items:
        keyword_el = item.select_one("div.mZ3RIc")
        search_volume_el = item.select_one("div.qNpYPd")
        
        if keyword_el and search_volume_el:
            keyword = keyword_el.get_text(strip=True).replace(" ", "")
            raw_search_volume = search_volume_el.get_text(strip=True)
            
            numeric_volume = 0
            try:
                processed_volume = raw_search_volume.replace("검색", "").replace("+회", "").strip()
                if "만" in processed_volume:
                    numeric_volume = int(float(processed_volume.replace("만", "")) * 10000)
                elif "천" in processed_volume:
                    numeric_volume = int(float(processed_volume.replace("천", "")) * 1000)
                else:
                    numeric_volume = int(processed_volume)
            except (ValueError, TypeError):
                numeric_volume = 0

            results.append({"keyword": keyword, "search_volume": numeric_volume})
            
    print(f"[trends] 총 {len(results)}개의 트렌드 키워드를 성공적으로 추출했습니다.")
    return results

if __name__ == "__main__":
    # 이 파일을 직접 실행할 경우, 테스트를 위해 browser_manager를 사용합니다.
    from browser_manager import start_browser, get_browser, stop_browser
    
    async def test_run():
        await start_browser()
        browser_instance = get_browser()
        if browser_instance:
            trending_keywords = await get_trending_keywords(browser_instance)
            if trending_keywords:
                print("\n✅ Google Trends 실시간 인기 검색어 (한국)")
                pprint(trending_keywords)
            else:
                print("데이터를 가져오는 데 실패했습니다.")
        await stop_browser()
    
    asyncio.run(test_run())