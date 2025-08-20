from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
import asyncio
from contextlib import asynccontextmanager

from services.browser_manager import start_browser, stop_browser, get_browser
from services.google_trends_scraper import get_trending_keywords
from DB.database import get_db
from DB import crud

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 실행
    await start_browser()
    yield
    # 종료 시 실행
    await stop_browser()

app = FastAPI(
    title="Extractor API Server",
    description="Provides access to real-time Google Trends data and saves to database.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", summary="Root Endpoint", description="API 서버의 상태를 확인하는 기본 엔드포인트입니다.")
async def read_root():
    return {"message": "Welcome to the Extractor API Server!"}

@app.get("/trends/korea", 
         response_model=Dict[str, Any],
         summary="Get Google Trends and Save to DB",
         description="Google Trends 페이지에서 최신 인기 검색어를 스크레이핑하여 DB에 저장하고 결과를 반환합니다.")
async def trends():
    browser = await get_browser()
    if not browser:
        raise HTTPException(status_code=500, detail="Browser is not available. Check server logs.")
    
    try:
        trending_keywords = await get_trending_keywords(browser)
        if not trending_keywords:
            raise HTTPException(status_code=500, detail="Failed to scrape trending keywords. The structure of the page might have changed.")
        
        with get_db() as db:
            saved_keywords = crud.clear_and_save_trend_keywords(db, trending_keywords)
            
        return {
            "message": f"{len(saved_keywords)}개의 트렌드 키워드가 DB에 저장되었습니다.",
            "saved_count": len(saved_keywords),
            "keywords": trending_keywords
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}") 