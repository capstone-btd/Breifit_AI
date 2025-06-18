from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
import asyncio

# Import services
from services.browser_manager import start_browser, stop_browser, get_browser
from services.google_trends_scraper import get_trending_keywords

# Create a FastAPI app instance
app = FastAPI(
    title="Extractor API Server",
    description="Provides access to real-time Google Trends data.",
    version="1.0.0"
)

# App event handlers
@app.on_event("startup")
async def startup_event():
    """
    기능: FastAPI 서버가 시작될 때 Playwright 브라우저 인스턴스를 시작합니다.
    """
    await start_browser()
    # Playwright의 브라우저 실행 파일 설치 (Docker 환경에서 필요)
    # 로컬에서 실행할 때는 보통 필요없지만, Dockerfile에서 설치하도록 권장됩니다.
    # 여기서는 안전하게 호출해줍니다.
    try:
        process = await asyncio.create_subprocess_shell(
            "playwright install --with-deps",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            print(f"Playwright install failed: {stderr.decode()}")
        else:
            print(f"Playwright install successful: {stdout.decode()}")
    except Exception as e:
        print(f"An error occurred during playwright install: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    기능: FastAPI 서버가 종료될 때 Playwright 브라우저 인스턴스를 정리합니다.
    """
    await stop_browser()

# API Endpoints
@app.get("/", summary="Root Endpoint", description="API 서버의 상태를 확인하는 기본 엔드포인트입니다.")
async def read_root():
    """
    기능: API 서버가 실행 중인지 확인하기 위한 간단한 메시지를 반환합니다.
    input: 없음
    output: 환영 메시지 (JSON)
    """
    return {"message": "Welcome to the Extractor API Server!"}


@app.get("/trends", 
         response_model=List[Dict[str, Any]],
         summary="Get Google Trends",
         description="Google Trends 페이지에서 최신 인기 검색어 목록을 스크레이핑하여 반환합니다.")
async def trends():
    """
    기능:
    실시간 구글 트렌드 인기 검색어 순위를 가져옵니다.
    내부적으로 공유된 브라우저 인스턴스를 사용하여 데이터를 스크레이핑합니다.

    input:
    없음

    output:
    성공 시: 트렌드 키워드와 검색량 목록 (List[Dict])
    실패 시: HTTP 500 에러
    """
    browser = get_browser()
    if not browser:
        raise HTTPException(status_code=500, detail="Browser is not available. Check server logs.")
    
    try:
        trending_keywords = await get_trending_keywords(browser)
        if not trending_keywords:
            # 스크레이퍼가 빈 리스트를 반환하는 것은 스크레이핑 실패를 의미할 수 있음
            raise HTTPException(status_code=500, detail="Failed to scrape trending keywords. The structure of the page might have changed.")
        return trending_keywords
    except Exception as e:
        # get_trending_keywords 내에서 발생할 수 있는 예외 처리
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}") 