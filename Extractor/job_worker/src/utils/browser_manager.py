from playwright.async_api import async_playwright, Browser, Playwright, Page
from typing import Optional
import asyncio

# --- For FastAPI server ---
_playwright_fastapi: Optional[Playwright] = None
_browser_fastapi: Optional[Browser] = None

async def start_browser():
    """
    FastAPI 서버를 위한 전역 Playwright 및 Browser 인스턴스를 시작합니다.
    """
    global _playwright_fastapi, _browser_fastapi
    if _browser_fastapi is None:
        print("[BrowserManager] FastAPI 서버용 브라우저를 시작합니다...")
        _playwright_fastapi = await async_playwright().start()
        _browser_fastapi = await _playwright_fastapi.chromium.launch(headless=True)
        print("[BrowserManager] FastAPI 서버용 브라우저가 성공적으로 실행되었습니다.")

async def stop_browser():
    """
    FastAPI 서버를 위한 전역 Browser 및 Playwright 인스턴스를 중지합니다.
    """
    global _playwright_fastapi, _browser_fastapi
    if _browser_fastapi:
        await _browser_fastapi.close()
        _browser_fastapi = None
    if _playwright_fastapi:
        await _playwright_fastapi.stop()
        _playwright_fastapi = None
    print("[BrowserManager] FastAPI 서버용 브라우저 리소스가 정리되었습니다.")

def get_browser() -> Optional[Browser]:
    """
    FastAPI 서버에서 실행 중인 전역 브라우저 인스턴스를 반환합니다.
    """
    return _browser_fastapi


# --- Singleton Pattern for Local Pipeline ---
class BrowserManager:
    """
    로컬 파이프라인을 위한 Playwright 브라우저 인스턴스를 관리하는 싱글톤 클래스.
    """
    _instance = None
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _lock = asyncio.Lock()
    _active_pages = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    async def _get_browser(self) -> Browser:
        async with self._lock:
            if self._browser is None:
                print("[BrowserManager] 로컬 파이프라인용 새 브라우저 인스턴스를 시작합니다...")
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                print("[BrowserManager] 로컬 파이프라인용 브라우저가 성공적으로 실행되었습니다.")
        return self._browser

    async def get_page(self) -> Page:
        browser = await self._get_browser()
        async with self._lock:
            self._active_pages += 1
            print(f"[BrowserManager] 새 페이지를 제공합니다. (활성 페이지: {self._active_pages})")
        return await browser.new_page()

    async def release_page(self, page: Page):
        await page.close()
        should_shutdown = False
        async with self._lock:
            self._active_pages -= 1
            print(f"[BrowserManager] 페이지를 닫았습니다. (활성 페이지: {self._active_pages})")
            if self._active_pages == 0 and self._browser is not None:
                should_shutdown = True
        
        if should_shutdown:
            await self.shutdown()
    
    async def shutdown(self):
        async with self._lock:
            if self._browser:
                print("[BrowserManager] 모든 작업이 완료되어 로컬 파이프라인용 브라우저를 종료합니다.")
                await self._browser.close()
                await self._playwright.stop()
                self._browser = None
                self._playwright = None

def get_browser_manager() -> BrowserManager:
    """
    BrowserManager의 싱글톤 인스턴스를 반환하는 팩토리 함수.
    """
    return BrowserManager() 