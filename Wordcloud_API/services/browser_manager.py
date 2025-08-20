from playwright.async_api import async_playwright, Browser, Playwright
from typing import Optional
import asyncio

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None

async def start_browser():
    """
    전역 Playwright 및 Browser 인스턴스를 시작합니다. (비동기 방식)
    서버 시작 시 한번만 호출됩니다.
    """
    global _playwright, _browser
    if _browser is None:
        print("[BrowserManager] Playwright (Async)를 시작하고 브라우저를 실행합니다...")
        try:
            print("[BrowserManager] 1/4: async_playwright() 컨텍스트 시작 시도...")
            _playwright = await async_playwright().start()
            print("[BrowserManager] 2/4: async_playwright() 컨텍스트 시작 완료.")

            print("[BrowserManager] 3/4: chromium.launch() 브라우저 실행 시도...")
            _browser = await _playwright.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            print("[BrowserManager] 4/4: 브라우저가 성공적으로 실행되었습니다.")
        except Exception as e:
            print(f"[BrowserManager] 브라우저 시작 중 치명적 오류 발생: {e}")
            if _playwright:
                await _playwright.stop()
            _playwright = None
            _browser = None

async def stop_browser():
    global _playwright, _browser
    if _browser:
        try:
            print("[BrowserManager] 브라우저를 닫습니다...")
            await _browser.close()
        except Exception as e:
            print(f"[BrowserManager] 브라우저를 닫는 중 오류 발생: {e}")
        finally:
            _browser = None

    if _playwright:
        try:
            print("[BrowserManager] Playwright를 중지합니다...")
            await _playwright.stop()
        except Exception as e:
            print(f"[BrowserManager] Playwright를 중지하는 중 오류 발생: {e}")
        finally:
            _playwright = None
    print("[BrowserManager] 모든 브라우저 리소스가 정리되었습니다.")


async def get_browser() -> Optional[Browser]:
    """
    실행 중인 전역 브라우저 인스턴스를 비동기적으로 반환합니다.
    브라우저가 초기화될 때까지 최대 60초간 대기합니다.
    """
    for i in range(1200):  # 0.1초씩 600번, 총 60초간 시도
        if _browser is not None and _browser.is_connected():
            return _browser
        await asyncio.sleep(0.1)
    
    print("[BrowserManager] 경고: 120초 내에 브라우저를 사용할 수 없습니다.")
    return None