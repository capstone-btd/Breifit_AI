import asyncio
import yaml
import os
import sys
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
from typing import Dict, Any
from slugify import slugify
import aiohttp
import base64

# DB 연동을 위한 모듈 import
from sqlalchemy.orm import Session
from DB.database import SessionLocal
from DB import crud, models

# 프로젝트 루트 경로
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(current_dir)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Collector 클래스 import
from src.collection.cnn_collector import CnnCollector
from src.collection.bbc_collector import BBCCollector
from src.collection.guardian_collector import GuardianCollector
from src.collection.thetimes_collector import TheTimesCollector
from src.collection.yonhap_collector import YonhapCollector
from src.collection.chosun_collector import ChosunCollector
from src.collection.joongang_collector import JoongangCollector
from src.collection.donga_collector import DongaCollector
from src.collection.hankyoreh_collector import HankyorehCollector
from src.collection.kyunghyang_collector import KyunghyangCollector
from src.utils.text_processing import preprocess_text_simple
from src.utils.logger import setup_logger
from models.translation.nllb_translator import NllbTranslator

# 설정 파일 경로
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')
RAW_DATA_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

# Collector 클래스 매핑
COLLECTOR_CLASSES = {
    'cnn': CnnCollector,
    'bbc': BBCCollector,
    'the_guardian': GuardianCollector,
    'the_times': TheTimesCollector,
    '연합': YonhapCollector,
    '조선': ChosunCollector,
    '중앙': JoongangCollector,
    '동아': DongaCollector,
    '한겨레': HankyorehCollector,
    '경향': KyunghyangCollector
}

# 번역기 인스턴스 - None으로 초기화하고, 필요할 때 생성
translator: NllbTranslator = None

def get_translator() -> NllbTranslator:
    """번역기 인스턴스를 가져온다 (없으면 새로 생성). 싱글턴 패턴."""
    global translator
    if translator is None:
        print("[Translator] 번역기 인스턴스가 없으므로 새로 생성합니다...")
        try:
            translator = NllbTranslator()
            model_info = translator.get_model_info()
            print(f"[Translator] 번역기 로드 완료: {model_info['model_name']}")
        except Exception as e:
            print(f"[Translator] 번역기 초기화 실패: {e}")
            translator = None # 실패 시 다시 None으로 설정
    return translator

def get_collector_for_site(site_name: str, site_config: dict) -> Any:
    """사이트 이름에 해당하는 Collector 인스턴스 생성"""
    collector_class = COLLECTOR_CLASSES.get(site_name.lower())
    if not collector_class:
        print(f"경고: '{site_name}'에 대한 Collector를 찾을 수 없습니다.")
        return None
    return collector_class()

def load_config(config_path: str) -> Dict:
    """설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"설정 파일 로드 완료: {os.path.abspath(config_path)}")
        return config
    except Exception as e:
        print(f"설정 파일 로드 실패: {e}")
        return {}

def get_output_path(base_dir: str, category_name: str, filename: str, collection_time_str: str) -> str:
    """기사 저장 경로 생성 (카테고리 폴더에 바로 저장)"""
    path = os.path.join(base_dir, collection_time_str, category_name)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, filename)

async def save_json_async(data: dict, file_path: str) -> None:
    """기사 데이터를 JSON 파일로 비동기 저장"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"파일 저장 실패 ({file_path}): {e}")
        raise

async def download_and_encode_image(session: aiohttp.ClientSession, url: str, retries: int = 2, delay: int = 2) -> str | None:
    """URL에서 이미지를 비동기적으로 다운로드하고 Base64로 인코딩합니다. (재시도 로직 포함)"""
    if not url or not url.startswith('http'):
        return None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(retries + 1):
        try:
            async with session.get(url, timeout=20, headers=headers) as response: # 타임아웃 20초로 증가
                response.raise_for_status()
                image_bytes = await response.read()
                return base64.b64encode(image_bytes).decode('utf-8')
        except asyncio.TimeoutError:
            print(f"  - 경고: 이미지 다운로드 시간 초과 (시도 {attempt + 1}/{retries + 1}), URL: {url}")
        except Exception as e:
            print(f"  - 경고: 이미지 다운로드 중 오류 발생 (시도 {attempt + 1}/{retries + 1}): {e}, URL: {url}")
        
        if attempt < retries:
            await asyncio.sleep(delay) # 재시도 전 잠시 대기
            
    return None

async def preprocess_article(article: dict, press_company: str) -> dict:
    """기사 데이터 전처리 (번역 포함)"""
    if not article or not isinstance(article, dict):
        return None

    if not article.get('title') or not article.get('url'):
        print(f"경고: 필수 정보(제목 또는 URL)가 없는 기사가 있어 건너뜁니다: {article}")
        return None

    # press_company를 설정 파일의 키(예: '중앙')로 설정
    article['source'] = press_company

    # Base64 인코딩 로직이 사라졌으므로, 이미지 URL은 그대로 유지됩니다.
    # main_image_url 키를 image_url로 변경하여 DB 스키마와 맞춥니다.
    if 'main_image_url' in article:
        article['image_url'] = article.pop('main_image_url')

    original_article_text = article.get('article_text', '')
    if original_article_text:
        processed_text = preprocess_text_simple(original_article_text)
        # 키 이름을 'body'로 변경
        article['body'] = processed_text
        print(f"  - '{article['title'][:30]}' 기사 전처리 완료.")
    else:
        article['body'] = ""
    
    # 더 이상 사용되지 않는 'article_text' 키 삭제
    if 'article_text' in article:
        del article['article_text']

    if len(article.get('body', '').strip()) < 30:
        print(f"  - 경고: 최종 기사 내용이 30자 미만이라 저장하지 않습니다. (제목: '{article['title'][:30]}...')")
        return None

    # 번역 처리 (영어 기사인 경우)
    current_translator = get_translator()
    if current_translator and article.get('body'):
        english_chars = sum(1 for c in article['body'] if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in article['body'] if c.isalpha())
        
        if total_chars > 0 and english_chars / total_chars > 0.7:
            try:
                # 기사 본문 번역
                translated_text = current_translator.translate(article['body'])
                article['body'] = translated_text
                print(f"  - '{article['title'][:30]}' 기사 본문 번역 완료.")
                
                # 제목 번역
                translated_title = current_translator.translate(article['title'])
                article['title'] = translated_title
                print(f"  - '{article['title'][:30]}' 제목 번역 완료.")
                
            except Exception as e:
                print(f"  - 경고: 번역 중 오류 발생: {e}")

    return article

async def run_collection_for_site(site_name: str, site_config: dict, api_call_time: datetime, session: aiohttp.ClientSession, db: Session) -> int:
    """
    특정 언론사의 모든 카테고리에서 기사 수집.
    성공적으로 DB에 추가된 기사의 수를 반환합니다.
    """
    print(f"\n[run_collection] {site_name.upper()} 수집 시작...")
    
    collector = get_collector_for_site(site_name, site_config)
    if not collector: return 0

    categories_config = site_config.get('categories', {})
    if not categories_config:
        print(f"경고: {site_name}에 대한 카테고리 설정이 없습니다. 건너뜁니다.")
        return 0

    category_tasks = []
    for category_display_name, category_path_segment in categories_config.items():
        if isinstance(category_path_segment, list):
            for path_segment in category_path_segment:
                category_tasks.append(collector.collect_by_category(category_display_name, path_segment))
        elif isinstance(category_path_segment, str):
            category_tasks.append(collector.collect_by_category(category_display_name, category_path_segment))

    if not category_tasks:
        print(f"경고: {site_name}에 대한 유효한 카테고리 설정이 없습니다.")
        return 0

    category_results = await asyncio.gather(*category_tasks, return_exceptions=True)
    
    newly_added_count = 0

    for result in category_results:
        if isinstance(result, Exception):
            print(f"카테고리 수집 중 오류 발생: {result}")
            continue
            
        articles_data = result
        if not articles_data:
            continue

        category_display_name = articles_data[0].get('category', 'etc') if articles_data else 'etc'
        print(f"카테고리 '{category_display_name}' ({site_name})에서 {len(articles_data)}개 기사 수집 완료. 전처리 및 DB 저장 시작...")
        
        async def process_and_save_to_db(article_data: dict) -> bool:
            """단일 기사를 전처리하고 DB에 저장. 성공 시 True 반환"""
            if not article_data or not isinstance(article_data, dict):
                return False

            title = article_data.get('title', '제목 없음')
            try:
                processed_article = await preprocess_article(article_data, site_name)
                if processed_article:
                    processed_article['created_at'] = api_call_time # API 호출 시간 추가
                    # crud 함수는 동기 함수이므로 to_thread로 실행
                    created_article = await asyncio.to_thread(
                        crud.create_article_with_image, db, processed_article
                    )
                    if created_article:
                        print(f"  - DB 저장 완료: '{created_article.title[:30]}...' (ID: {created_article.id})")
                        return True
                    # create_article_with_image가 None을 반환하는 경우 (예: 중복)은 이미 crud에서 로그를 남기므로 여기서는 별도 처리 안 함
                else:
                    print(f"  - 기사 '{title[:30]}...' 전처리 후 내용이 없어 저장하지 않습니다.")
            
            except Exception as e:
                # 상세한 오류 로깅
                print(f"!!! 기사 '{title[:30]}...' 처리/저장 중 심각한 오류 발생: {e}")
                import traceback
                traceback.print_exc()

            return False

        # --- 병렬 처리 제거: 순차적으로 기사 처리 ---
        for article_data in articles_data:
            success = await process_and_save_to_db(article_data)
            if success:
                newly_added_count += 1
    
    return newly_added_count

async def run_collection_pipeline() -> int:
    """
    전체 뉴스 수집 파이프라인을 실행하는 메인 함수.
    언론사별로 순차적으로 실행하며, 최종적으로 새로 추가된 기사의 총 수를 반환합니다.
    """
    print("\n[run_collection] 전체 뉴스 수집 파이프라인 시작...")
    config = load_config(CONFIG_FILE_PATH)
    if not config:
        print("[run_collection] 에러: 설정 파일을 찾을 수 없어 파이프라인을 중단합니다.")
        return 0

    api_call_time = datetime.now() # API 호출 시점 기록
    collection_time_str = api_call_time.strftime("%Y%m%d_%H%M%S")
    print(f"[run_collection] 뉴스 수집 시작 시간: {collection_time_str}")

    db = SessionLocal()
    total_added_count = 0
    try:
        async with aiohttp.ClientSession() as session:
            for site_name, site_config in config['sites'].items():
                site_added_count = await run_collection_for_site(
                    site_name, site_config, api_call_time, session, db
                )
                total_added_count += site_added_count
    finally:
        db.close()
        print("[run_collection] 데이터베이스 세션을 닫았습니다.")

    print(f"\n[run_collection] 모든 사이트의 뉴스 수집 완료. 총 {total_added_count}개의 새 기사가 DB에 저장되었습니다.")
    return total_added_count

if __name__ == "__main__":
    setup_logger()
    logging.info("="*50)
    logging.info("뉴스 기사 수집 스크립트 시작")
    
    added_count = asyncio.run(run_collection_pipeline())

    print("\n--- 수집 완료 ---")
    print(f"새롭게 DB에 추가된 기사 수: {added_count}")
    
    logging.info("뉴스 기사 수집 스크립트 종료")
    logging.info("="*50 + "\n")