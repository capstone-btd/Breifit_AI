import os
from fastapi import FastAPI
from Extractor.scripts.google_trends import get_trending_keywords

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Google Trends Scraper API"}

@app.get("/trends/korea")
def get_korea_trends():
    """
    Google Trends 실시간 인기 검색어 (한국)를 스크래핑하여 반환합니다.
    """
    trends = get_trending_keywords()
    return {"trends": trends}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 