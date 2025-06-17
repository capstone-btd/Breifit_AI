import asyncio
import sys

# Windows에서 Playwright 비동기 실행 시 발생하는 NotImplementedError 해결
# 다른 어떤 import보다도 먼저 실행되어야 함.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from contextlib import asynccontextmanager
import logging

# Add the parent directory to the path to allow relative imports
# 프로젝트 루트 경로를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Google Trends 스크립트 import
from scripts.google_trends import get_trending_keywords
# 데이터 수집 파이프라인 import
from scripts.run_collection import run_collection_pipeline
# 데이터 처리 파이프라인 import
from scripts.run_processing import run_processing_pipeline
from src.utils.browser_manager import start_browser, stop_browser, get_browser
from src.utils.logger import setup_logger
from DB.database import engine, Base
from DB import models

# 기본 로거 설정
setup_logger()

# 서버 시작 시 데이터베이스 테이블 생성
models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시
    print("[Main] 애플리케이션 시작... (Async) 브라우저를 실행합니다.")
    await start_browser()
    yield
    # 애플리케이션 종료 시
    print("[Main] 애플리케이션 종료... 브라우저를 닫습니다.")
    await stop_browser()

app = FastAPI(lifespan=lifespan)

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

    # data/raw/{collection_time_str}/{category_name}/{filename}.json 구조를 순회
    for collection_folder in os.listdir(RAW_DATA_DIR):
        collection_path = os.path.join(RAW_DATA_DIR, collection_folder)
        if not os.path.isdir(collection_path): continue

        for category_name in os.listdir(collection_path):
            category_path = os.path.join(collection_path, category_name)
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

@app.post("/collect", summary="뉴스 수집 및 로컬 저장", description="설정 파일에 명시된 모든 언론사의 뉴스를 수집하여 로컬 파일 시스템에 JSON으로 저장합니다.")
async def run_collection_endpoint():
    logger = logging.getLogger(__name__)
    logger.info("'/collect' 엔드포인트 호출됨. 뉴스 수집 및 로컬 저장 파이프라인 시작.")
    
    try:
        # 로컬에 파일로 저장하는 파이프라인 실행
        files_saved_count = await run_collection_pipeline()
        
        logger.info(f"총 {files_saved_count}개의 새 기사 수집 및 로컬 저장 완료.")
        return JSONResponse(
            status_code=200,
            content={"message": f"총 {files_saved_count}개의 새 기사가 로컬에 저장되었습니다.", "files_saved_count": files_saved_count}
        )
    except Exception as e:
        logger.error(f"'/collect' 엔드포인트 처리 중 심각한 오류 발생: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"뉴스 수집 파이프라인 실행 중 오류가 발생했습니다: {e}"
        )

@app.post("/process", summary="수집된 뉴스 처리 및 DB 저장", description="로컬에 저장된 뉴스 JSON 파일들을 읽어 그룹핑, 요약 후 DB에 최종 저장합니다.")
async def run_processing_endpoint():
    logger = logging.getLogger(__name__)
    logger.info("'/process' 엔드포인트 호출됨. 기사 처리 및 DB 저장 파이프라인 시작.")

    try:
        # 동기 함수인 run_processing_pipeline을 실행합니다.
        # FastAPI는 이를 자동으로 스레드 풀에서 실행하여 이벤트 루프를 막지 않습니다.
        run_processing_pipeline()
        
        # run_processing_pipeline 내부에서 상세한 로그를 남기므로, 여기서는 성공 메시지만 반환합니다.
        # 처리된 기사 수를 정확히 반환하려면 run_processing_pipeline 수정이 필요합니다.
        return JSONResponse(
            status_code=200,
            content={"message": "기사 처리 및 DB 저장 파이프라인이 성공적으로 실행되었습니다. 상세 내용은 서버 로그를 확인하세요."}
        )
    except Exception as e:
        logger.error(f"'/process' 엔드포인트 처리 중 심각한 오류 발생: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"기사 처리 파이프라인 실행 중 오류가 발생했습니다: {e}"
        )

@app.get("/trends/korea")
async def get_korea_trends():
    """
    한국 실시간 트렌드 키워드 조회 (Playwright 비동기 방식 - 브라우저 재사용)
    input : 없음
    output : 한국 실시간 트렌드 키워드 (JSON형식)
    """
    print("\n[main.py] /trends/korea 엔드포인트 요청 수신")
    
    browser = get_browser()
    if not browser:
        print("[main.py] 에러: 브라우저 인스턴스를 사용할 수 없습니다.")
        raise HTTPException(status_code=500, detail="서버에 브라우저가 준비되지 않았습니다. 서버 로그를 확인해주세요.")

    try:
        trends_data = await get_trending_keywords(browser)
        if trends_data:
            print("[main.py] Playwright 스크레이핑 성공. JSON 응답을 반환합니다.")
            return JSONResponse(content={"keywords": trends_data})
        else:
            print("[main.py] Playwright 스크레이퍼가 데이터를 반환하지 못했거나 실패했습니다.")
            raise HTTPException(status_code=500, detail="스크래핑을 통해 구글 트렌드 데이터를 가져오는데 실패했습니다.")
            
    except Exception as e:
        print(f"[main.py] /trends/korea 엔드포인트 처리 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"트렌드 데이터 조회 중 서버 오류 발생: {str(e)}")

if __name__ == "__main__":
    # 이 파일을 직접 실행하면 Uvicorn 서버가 시작됩니다.
    # Windows에서 asyncio 정책 설정 후 서버를 실행하기 위해 이 방식을 사용합니다.
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)