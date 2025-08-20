import asyncio
import os
import sys
import torch

# ===== Konlpy가 Mecab을 찾을 수 있도록 경로 설정 (SUDO 권한이 없을 때) =====
# Mecab-ko가 설치된 경로를 직접 지정해줍니다.
os.environ['MECAB_PATH'] = '/usr/local/bin/mecab'
device='cuda' if torch.cuda.is_available() else 'cpu'
print(f"Using device: {device}")
# ======================================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from scripts.run_collection_wordcloud import run_wordcloud_collection_pipeline
from scripts.run_processing_for_wc import run_processing_for_wc_pipeline
from src.utils.logger import setup_logger

async def main():
    logger = setup_logger(name="wordcloud_pipeline_coordinator", level="INFO")
    logger.info("======= WordCloud 기반 전체 데이터 파이프라인 작업을 시작합니다 =======")

    # --- 1단계: WordCloud 기반 데이터 수집 ---
    logger.info("[WC_PIPELINE] 1단계 시작: WordCloud 키워드 기반 데이터 수집")
    collection_output_dir = await run_wordcloud_collection_pipeline()
    
    if not collection_output_dir:
        logger.info("[WC_PIPELINE] 1단계 완료: WordCloud 기반으로 새로 수집된 데이터가 없어 파이프라인을 종료합니다.")
        return
    
    logger.info(f"[WC_PIPELINE] 1단계 완료: WordCloud 기반 데이터 수집 완료. 결과물 위치: {collection_output_dir}")

    # --- 2단계: 데이터 처리 및 저장 ---
    logger.info("[WC_PIPELINE] 2단계 시작: WordCloud 수집 데이터 처리 및 DB 저장")
    try:
        run_processing_for_wc_pipeline(collection_output_dir)
        logger.info("[WC_PIPELINE] 2단계 완료: WordCloud 데이터 처리 성공.")
    except Exception as e:
        logger.error(f"[WC_PIPELINE] 2단계 실행 중 심각한 오류 발생: {e}", exc_info=True)

    logger.info("======= WordCloud 기반 전체 데이터 파이프라인 작업이 성공적으로 완료되었습니다 =======")

if __name__ == "__main__":
    # Windows에서 asyncio 이벤트 루프 정책 설정 (Jupyter 환경 등에서 발생하는 에러 방지)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main()) 