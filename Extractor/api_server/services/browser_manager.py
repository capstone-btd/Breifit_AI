from playwright.async_api import async_playwright, Browser, Playwright
from typing import Optional

# FastAPI 애플리케이션 전체에서 공유될 단일 인스턴스
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
            _playwright = await async_playwright().start()
            # For Docker, we need to run with --no-sandbox
            _browser = await _playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            print("[BrowserManager] 브라우저가 성공적으로 실행되었습니다.")
        except Exception as e:
            print(f"[BrowserManager] 브라우저 시작 중 오류 발생: {e}")
            if _playwright:
                await _playwright.stop()
            _playwright = None
            _browser = None

async def stop_browser():
    """
    전역 Browser 및 Playwright 인스턴스를 중지합니다. (비동기 방식)
    서버 종료 시 한번만 호출됩니다.
    """
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


def get_browser() -> Optional[Browser]:
    """
    실행 중인 전역 브라우저 인스턴스를 반환합니다.
    """
    if _browser is None:
        print("[BrowserManager] 경고: 브라우저가 실행 중이 아니지만 요청이 들어왔습니다.")
        return None
    return _browser 