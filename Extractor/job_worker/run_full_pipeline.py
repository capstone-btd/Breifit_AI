import asyncio
import os
import sys

# 현재 파일의 디렉토리를 기준으로 프로젝트 루트 경로를 찾아 sys.path에 추가
# 이렇게 하면 Extractor/job_worker 폴더 어디에서 실행하든 모듈을 찾을 수 있습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from scripts.run_collection import run_collection_pipeline
from scripts.run_processing import run_processing_pipeline
from src.utils.logger import setup_logger

async def main():
    logger = setup_logger(name="pipeline_coordinator", level="INFO")
    logger.info("======= 전체 데이터 파이프라인 작업을 시작합니다 =======")

    # --- 1단계: 데이터 수집 ---
    logger.info("[PIPELINE] 1단계 시작: 데이터 수집")
    collection_output_dir = await run_collection_pipeline()
    
    if not collection_output_dir:
        logger.info("[PIPELINE] 1단계 완료: 새로 수집된 데이터가 없어 파이프라인을 종료합니다.")
        return
    
    logger.info(f"[PIPELINE] 1단계 완료: 데이터 수집 완료. 결과물 위치: {collection_output_dir}")

    # --- 2단계: 데이터 처리 및 저장 ---
    logger.info("[PIPELINE] 2단계 시작: 데이터 처리 및 DB 저장")
    try:
        run_processing_pipeline(collection_output_dir)
        logger.info("[PIPELINE] 2단계 완료: 데이터 처리 성공.")
    except Exception as e:
        logger.error(f"[PIPELINE] 2단계 실행 중 심각한 오류 발생: {e}", exc_info=True)

    logger.info("======= 전체 데이터 파이프라인 작업이 성공적으로 완료되었습니다 =======")

if __name__ == "__main__":
    # Windows에서 asyncio 이벤트 루프 정책 설정 (Jupyter 환경 등에서 발생하는 에러 방지)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main()) 