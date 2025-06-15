import asyncio
import json
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any

# Add the parent directory to the path to allow relative imports
# 프로젝트 루트 경로를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Google Trends 스크립트 import
from scripts.google_trends import get_trending_keywords
# 데이터 수집 파이프라인 import
from scripts.run_collection import run_collection_pipeline

app = FastAPI()

# 상수 정의
# Extractor 폴더가 프로젝트 루트라고 가정
EXTRACTOR_ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(EXTRACTOR_ROOT, "data", "raw")

def get_all_collected_data() -> List[Dict[str, Any]]:
    """
    기능: data/raw 폴더의 모든 JSON 파일 내용을 읽어 리스트로 반환한다.
    input: 없음
    output: 모든 기사 데이터가 담긴 리스트 (List[Dict[str, Any]])
    """
    print("[main.py] 수집된 모든 데이터 읽기 시작...")
    all_data = []
    if not os.path.exists(RAW_DATA_DIR):
        print(f"[main.py] 경고: 데이터 디렉토리({RAW_DATA_DIR})가 존재하지 않습니다.")
        return all_data

    # data/raw/{collection_time_str}/{site_name}/{category_name}/{filename}.json 구조를 순회
    for collection_folder in os.listdir(RAW_DATA_DIR):
        collection_path = os.path.join(RAW_DATA_DIR, collection_folder)
        if not os.path.isdir(collection_path): continue

        for site_name in os.listdir(collection_path):
            site_path = os.path.join(collection_path, site_name)
            if not os.path.isdir(site_path): continue

            for category_name in os.listdir(site_path):
                category_path = os.path.join(site_path, category_name)
                if not os.path.isdir(category_path): continue

                for filename in os.listdir(category_path):
                    if filename.endswith(".json"):
                        file_path = os.path.join(category_path, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                all_data.append(data)
                        except Exception as e:
                            print(f"[main.py] JSON 파일 읽기/파싱 오류 {file_path}: {e}")
    print(f"[main.py] 총 {len(all_data)}개의 데이터를 읽었습니다.")
    return all_data


@app.get("/collect", response_model=List[Dict[str, Any]])
async def collect_and_get_data():
    """
    기능: 데이터 수집 파이프라인을 실행하고, 수집된 모든 데이터를 JSON으로 반환한다.
    input: 없음 (HTTP GET 요청)
    output: 수집된 전체 기사 데이터 (JSONResponse)
    """
    print("\n[main.py] /collect 엔드포인트 요청 수신")
    try:
        # 데이터 수집 파이프라인 직접 호출
        await run_collection_pipeline(raw_data_base_dir=RAW_DATA_DIR)
        
        # 수집된 데이터 읽기
        collected_data = get_all_collected_data()
        
        if not collected_data:
            print("[main.py] 데이터 수집 후 파일을 읽었지만 데이터가 없습니다.")
            return JSONResponse(status_code=404, content={"message": "데이터 수집은 완료되었으나, 반환할 데이터가 없습니다."})
            
        print(f"[main.py] 총 {len(collected_data)}개의 기사 데이터를 반환합니다.")
        return collected_data
    except Exception as e:
        print(f"[main.py] '/collect' 엔드포인트에서 예기치 않은 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"message": f"서버 내부 오류가 발생했습니다: {e}"})

@app.get("/trends/korea")
async def get_korea_trends():
    """
    한국 실시간 트렌드 키워드 조회 (Selenium 스크레이핑)
    input : 없음
    output : 한국 실시간 트렌드 키워드 (JSON형식)
    """
    print("Received request for /trends/korea. Starting NEW Selenium scraper...")
    try:
        trends_data = get_trending_keywords()
        if trends_data:
            print("Successfully scraped data. Returning JSON response.")
            return JSONResponse(content={"keywords": trends_data})
        else:
            print("Scraper returned no data or failed.")
            raise HTTPException(status_code=500, detail="스크래핑을 통해 구글 트렌드 데이터를 가져오는데 실패했습니다.")
            
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        raise HTTPException(status_code=500, detail=f"트렌드 데이터 조회 중 서버 오류 발생: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)