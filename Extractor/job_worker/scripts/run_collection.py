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

# DB 연동을 위한 모듈 import - 현재 단계에서는 사용하지 않으므로 주석 처리
# from sqlalchemy.orm import Session
# from DB.database import SessionLocal
# from DB import crud, models

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
# 수집된 기사를 저장할 기본 디렉토리
COLLECTED_ARTICLES_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'collected_articles')

# Collector 클래스 매핑
COLLECTOR_CLASSES = {
    'cnn': CnnCollector,
    'bbc': BBCCollector,
    'the_guardian': GuardianCollector,
    'the_times': TheTimesCollector,
    '연합뉴스': YonhapCollector,
    '조선일보': ChosunCollector,
    '중앙일보': JoongangCollector,
    '동아일보': DongaCollector,
    '한겨레': HankyorehCollector,
    '경향신문': KyunghyangCollector
}

# 번역기 인스턴스 - None으로 초기화하고, 필요할 때 생성
translator: NllbTranslator = None

def get_translator() -> NllbTranslator:
    """
    기능: 번역기(NllbTranslator)의 싱글턴 인스턴스를 반환합니다. 인스턴스가 없으면 새로 생성하고, 이미 있으면 기존 인스턴스를 반환합니다.
    input: 없음
    output: NllbTranslator 인스턴스 또는 초기화 실패 시 None
    """
    global translator
    if translator is None:
        print("[Translator] 번역기 인스턴스가 없으므로 새로 생성합니다...")
        try:
            translator = NllbTranslator()
            model_info = translator.get_model_info()
            print(f"[Translator] 번역기 로드 완료: {model_info['model_name']}")
        except Exception as e:
            print(f"[Translator] 번역기 초기화 실패: {e}")
            translator = None
    return translator

def get_collector_for_site(site_name: str, site_config: dict) -> Any:
    """
    기능: 사이트 이름에 해당하는 Collector 클래스의 인스턴스를 생성하여 반환합니다.
    input: site_name (언론사 이름), site_config (해당 언론사의 설정 딕셔너리)
    output: Collector 인스턴스 또는 None
    """
    collector_class = COLLECTOR_CLASSES.get(site_name.lower())
    if not collector_class:
        print(f"경고: '{site_name}'에 대한 Collector를 찾을 수 없습니다.")
        return None
    return collector_class()

def load_config(config_path: str) -> Dict:
    """
    기능: YAML 설정 파일을 로드하여 딕셔너리로 반환합니다.
    input: config_path (설정 파일의 경로)
    output: 설정 내용이 담긴 딕셔너리
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"설정 파일 로드 완료: {os.path.abspath(config_path)}")
        return config
    except Exception as e:
        print(f"설정 파일 로드 실패: {e}")
        return {}

def get_output_path(base_dir: str, category_name: str, filename: str, collection_time_str: str) -> str:
    """
    기능: 수집된 기사를 저장할 파일 경로를 생성합니다.
    input: base_dir (저장 기본 경로), category_name (기사 카테고리), filename (저장될 파일명), collection_time_str (수집 시간 문자열)
    output: 최종 저장 파일 경로 문자열
    """
    path = os.path.join(base_dir, collection_time_str, category_name)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, filename)

async def save_json_async(data: dict, file_path: str) -> None:
    """
    기능: 딕셔너리 데이터를 JSON 파일로 비동기적으로 저장합니다.
    input: data (저장할 딕셔너리), file_path (저장할 파일 경로)
    output: 없음
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"파일 저장 실패 ({file_path}): {e}")
        raise

async def download_and_encode_image(session: aiohttp.ClientSession, url: str, retries: int = 2, delay: int = 2) -> str | None:
    """
    기능: URL에서 이미지를 비동기적으로 다운로드하고 Base64로 인코딩합니다. 재시도 로직을 포함합니다.
    input: session (aiohttp.ClientSession), url (이미지 URL), retries (재시도 횟수), delay (재시도 간 지연 시간)
    output: Base64로 인코딩된 이미지 문자열 또는 실패 시 None
    """
    if not url or not url.startswith('http'):
        return None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(retries + 1):
        try:
            async with session.get(url, timeout=20, headers=headers) as response:
                response.raise_for_status()
                image_bytes = await response.read()
                return base64.b64encode(image_bytes).decode('utf-8')
        except asyncio.TimeoutError:
            print(f"  - 경고: 이미지 다운로드 시간 초과 (시도 {attempt + 1}/{retries + 1}), URL: {url}")
        except Exception as e:
            print(f"  - 경고: 이미지 다운로드 중 오류 발생 (시도 {attempt + 1}/{retries + 1}): {e}, URL: {url}")
        
        if attempt < retries:
            await asyncio.sleep(delay)
            
    return None

async def preprocess_article(article: dict, press_company: str) -> dict:
    """
    기능: 단일 기사 데이터를 전처리합니다. 영어 기사의 경우 번역을 수행하고, 불필요한 텍스트를 정리하며, 데이터 형식을 통일합니다.
    input: article (전처리할 기사 딕셔너리), press_company (언론사 이름)
    output: 전처리된 기사 딕셔너리 또는 처리할 수 없는 경우 None
    """
    if not article or not isinstance(article, dict):
        return None

    if not article.get('title') or not article.get('url'):
        print(f"경고: 필수 정보(제목 또는 URL)가 없는 기사가 있어 건너뜁니다: {article}")
        return None

    article['source'] = press_company

    if 'main_image_url' in article:
        article['image_url'] = article.pop('main_image_url')

    original_article_text = article.get('article_text', '')
    if original_article_text:
        processed_text = preprocess_text_simple(original_article_text)
        article['body'] = processed_text
        print(f"  - '{article['title'][:30]}' 기사 전처리 완료.")
    else:
        article['body'] = ""
    
    if 'article_text' in article:
        del article['article_text']

    if len(article.get('body', '').strip()) < 30:
        print(f"  - 경고: 최종 기사 내용이 30자 미만이라 저장하지 않습니다. (제목: '{article['title'][:30]}...')")
        return None

    current_translator = get_translator()
    if current_translator and article.get('body'):
        english_chars = sum(1 for c in article['body'] if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in article['body'] if c.isalpha())
        
        if total_chars > 0 and english_chars / total_chars > 0.7:
            print(f"  - 영어 기사로 판단되어 번역을 시작합니다: '{article.get('title', '제목 없음')[:30]}...'")
            try:
                translated_text = current_translator.translate(article['body'])
                article['body'] = translated_text
                
                translated_title = current_translator.translate(article['title'])
                article['title'] = translated_title
                print(f"  - 번역 완료: '{article['title'][:30]}...'")
                
            except Exception as e:
                print(f"  - 경고: 번역 중 오류 발생: {e}")

    return article

async def run_collection_for_site(site_name: str, site_config: dict, api_call_time: datetime, session: aiohttp.ClientSession) -> int:
    """
    기능: 특정 언론사의 모든 카테고리에서 기사를 수집하고 전처리하여 로컬에 JSON 파일로 저장합니다.
    input: site_name (언론사 이름), site_config (언론사 설정), api_call_time (API 호출 시간), session (aiohttp 클라이언트 세션)
    output: 성공적으로 로컬에 저장된 기사의 수
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
    
    files_saved_count = 0
    collection_time_str = api_call_time.strftime("%Y%m%d_%H%M%S")

    for result in category_results:
        if isinstance(result, Exception):
            print(f"카테고리 수집 중 오류 발생: {result}")
            continue
            
        articles_data = result
        if not articles_data:
            continue

        category_display_name = articles_data[0].get('category', 'etc') if articles_data else 'etc'
        print(f"카테고리 '{category_display_name}' ({site_name})에서 {len(articles_data)}개 기사 수집 완료. 전처리 및 로컬 저장 시작...")
        
        async def process_and_save_to_json(article_data: dict) -> bool:
            """단일 기사를 전처리하고 JSON 파일로 저장. 성공 시 True 반환"""
            if not article_data or not isinstance(article_data, dict):
                return False

            title = article_data.get('title', '제목 없음')
            try:
                processed_article = await preprocess_article(article_data, site_name)
                if processed_article:
                    processed_article['created_at'] = api_call_time.isoformat()
                    
                    safe_filename = slugify(processed_article['title'], max_length=50, allow_unicode=True)
                    if not safe_filename:
                        safe_filename = slugify(processed_article.get('source', 'untitled'), allow_unicode=True) + f"_{datetime.now().timestamp()}"
                    
                    filename = f"{safe_filename}.json"
                    output_path = get_output_path(
                        base_dir=COLLECTED_ARTICLES_BASE_DIR,
                        category_name=category_display_name,
                        filename=filename,
                        collection_time_str=collection_time_str
                    )
                    
                    await save_json_async(processed_article, output_path)
                    print(f"  - 로컬 저장 완료: {output_path}")
                    return True
            except Exception as e:
                print(f"  - 에러: '{title[:30]}...' 기사 처리/저장 중 오류 발생: {e}")
            return False

        save_tasks = [process_and_save_to_json(article) for article in articles_data]
        save_results = await asyncio.gather(*save_tasks)
        files_saved_count += sum(1 for r in save_results if r)

    print(f"[{site_name.upper()}] 총 {files_saved_count}개의 기사 로컬 저장 완료.")
    return files_saved_count

async def run_collection_pipeline() -> int:
    """
    기능: 설정 파일에 명시된 모든 활성화된 언론사를 대상으로 전체 뉴스 수집 파이프라인을 실행합니다.
    input: 없음
    output: 성공적으로 로컬에 저장된 총 기사의 수
    """
    logger = logging.getLogger(__name__)
    logger.info("전체 뉴스 수집 파이프라인 시작 (로컬 파일 저장 방식)...")
    
    config = load_config(CONFIG_FILE_PATH)
    if not config:
        logger.error("설정 파일 로딩 실패. 파이프라인을 중단합니다.")
        return 0

    api_call_time = datetime.now()
    total_files_saved = 0
    
    async with aiohttp.ClientSession() as session:
        site_tasks = []
        
        sites_to_crawl = config.get('sites', {})
        if not sites_to_crawl:
            logger.warning("설정 파일에 'sites' 목록이 비어있거나 없습니다.")
            return 0
            
        for site_name, site_config in sites_to_crawl.items():
            task = run_collection_for_site(site_name, site_config, api_call_time, session)
            site_tasks.append(task)
        
        results = await asyncio.gather(*site_tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            site_name = list(sites_to_crawl.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"'{site_name}' 사이트 처리 중 심각한 오류 발생: {result}", exc_info=result)
            else:
                total_files_saved += result

    logger.info(f"전체 뉴스 수집 파이프라인 완료. 총 {total_files_saved}개의 기사가 로컬에 저장되었습니다.")
    return total_files_saved

async def main():
    """
    기능: 스크립트가 직접 실행될 때 뉴스 수집 파이프라인을 실행하기 위한 메인 함수입니다.
    input: 없음
    output: 없음
    """
    setup_logger()
    
    print("스크립트 직접 실행: 전체 뉴스 수집 파이프라인 (로컬 저장) 시작...")
    saved_count = await run_collection_pipeline()
    print(f"\n스크립트 실행 완료. 총 {saved_count}개의 기사가 로컬에 저장되었습니다.")

if __name__ == "__main__":
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())