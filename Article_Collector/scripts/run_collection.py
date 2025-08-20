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
from google.cloud import storage
import io

# DB 연동을 위한 모듈 import - 현재 단계에서는 사용하지 않으므로 주석 처리
# from sqlalchemy.orm import Session
# from DB.database import SessionLocal
# from DB import crud, models

# 프로젝트 루트 경로 - 이제 run_full_pipeline.py에서 관리하므로 제거합니다.
# current_dir = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT = os.path.dirname(current_dir)
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

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

# 설정 파일 및 데이터 디렉토리 경로 - 프로젝트 루트를 기준으로 재설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')
COLLECTED_ARTICLES_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'collected_articles')

# GCS 설정 - 로컬 개발 환경에서도 실행 가능하도록 예외 처리
GCS_BUCKET_NAME = "betodi-gpu"  # 실제 GCS 버킷 이름
storage_client = None
bucket = None

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    print("[GCS] Google Cloud Storage 연결 성공")
except Exception as e:
    print(f"[GCS] Google Cloud Storage 연결 실패 (로컬 모드로 실행): {e}")
    storage_client = None
    bucket = None

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

async def upload_json_to_gcs_async(data: dict, gcs_path: str):
    """
    기능: 딕셔너리 데이터를 JSON으로 변환하여 GCS에 업로드하거나 로컬에 저장합니다.
    input: data (저장할 딕셔너리), gcs_path (GCS 내 저장 경로)
    output: 없음
    """
    # BUG FIX: 문자열 대신 bytes로 바로 처리하여 인코딩 문제를 원천 차단합니다.
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    
    # GCS가 사용 가능한 경우 GCS에 업로드
    # if bucket is not None:
    #     try:
    #         blob = bucket.blob(gcs_path)
    #         # file-like object를 사용하여 안정적으로 업로드
    #         with io.BytesIO(json_bytes) as stream:
    #             blob.upload_from_file(stream, content_type='application/json')
    #         print(f"  - GCS 업로드 성공: {gcs_path}")
    #         return
    #     except Exception as e:
    #         print(f"  - GCS 업로드 실패, 로컬로 저장: {e}")
    
    # GCS 사용 불가능하거나 업로드 실패 시 로컬에 저장
    # local_path = os.path.join(PROJECT_ROOT, 'data', 'backup', gcs_path)
    local_path = os.path.join(PROJECT_ROOT, 'Data', gcs_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    with open(local_path, 'wb') as f:
        f.write(json_bytes)
    print(f"  - 로컬 저장 완료: {local_path}")

async def run_collection_for_site(site_name: str, site_config: dict, collection_time_str: str, session: aiohttp.ClientSession) -> int:
    """
    기능: 특정 언론사의 모든 카테고리에서 기사를 수집하고 전처리하여 GCS에 JSON 파일로 저장합니다.
    input: site_name (언론사 이름), site_config (언론사 설정), collection_time_str (수집 시간 문자열), session (aiohttp 클라이언트 세션)
    output: 성공적으로 GCS에 저장된 기사의 수
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

    for result in category_results:
        if isinstance(result, Exception):
            print(f"카테고리 수집 중 오류 발생: {result}")
            continue
            
        articles_data = result
        if not articles_data:
            continue

        category_display_name = articles_data[0].get('category', 'etc') if articles_data else 'etc'
        print(f"카테고리 '{category_display_name}' ({site_name})에서 {len(articles_data)}개 기사 수집 완료. 전처리 및 GCS 저장 시작...")
        
        async def process_and_save_to_json(article_data: dict) -> bool:
            """
            기능: 단일 기사 데이터를 전처리하고 GCS에 JSON으로 저장합니다.
            output: 성공 시 True, 실패 시 False
            """
            processed_article = await preprocess_article(article_data, site_name)
            if not processed_article:
                return False

            filename = f"{slugify(processed_article.get('title', 'untitled'))}.json"
            category_name = processed_article.get('category', 'etc')
            
            # GCS 저장 경로 생성
            gcs_path = f"collected_articles/{collection_time_str}/{category_name}/{filename}"

            try:
                await upload_json_to_gcs_async(processed_article, gcs_path)
                return True
            except Exception as e:
                # 에러는 upload 함수에서 이미 출력됨
                return False

        save_tasks = [process_and_save_to_json(article) for article in articles_data]
        save_results = await asyncio.gather(*save_tasks)
        files_saved_count += sum(1 for r in save_results if r)

    print(f"[{site_name.upper()}] 총 {files_saved_count}개의 기사 GCS 저장 완료.")
    return files_saved_count

async def run_collection_pipeline() -> str | None:
    """
    기능: 설정 파일에 명시된 모든 언론사의 기사를 수집/처리하고 GCS에 저장합니다.
    output: 성공적으로 기사가 저장된 경우, GCS 내의 최상위 폴더 경로. 저장된 기사가 없으면 None.
    """
    logger = setup_logger()
    logger.info("======= Full Data Collection Job Succeeded =======")

    config = load_config(CONFIG_FILE_PATH)
    if not config:
        logger.error("설정 파일을 찾을 수 없거나 내용이 비어있어 수집을 중단합니다.")
        return None

    # 모든 사이트 수집 작업은 동일한 시간대 폴더에 저장됩니다.
    collection_time = datetime.now()
    collection_time_str = collection_time.strftime("%Y%m%d_%H%M%S")
    gcs_output_prefix = f"collected_articles/{collection_time_str}"

    # 비동기 HTTP 세션 생성
    async with aiohttp.ClientSession() as session:
        site_tasks = [
            run_collection_for_site(site_name, site_config, collection_time_str, session)
            for site_name, site_config in config.get('sites', {}).items()
        ]
        
        if not site_tasks:
            logger.warning("설정 파일에 수집할 사이트가 없습니다.")
            return None
        
        results = await asyncio.gather(*site_tasks)

    total_files_saved = sum(results)
    logger.info(f"전체 수집 완료. 총 {total_files_saved}개의 기사를 GCS에 저장했습니다.")
    
    if total_files_saved > 0:
        # logger.info(f"데이터 GCS 저장 위치: gs://{GCS_BUCKET_NAME}/{gcs_output_prefix}")
        local_output_path = os.path.join(PROJECT_ROOT, 'Data', gcs_output_prefix)
        logger.info(f"데이터 로컬 저장 위치: {local_output_path}")
        return local_output_path
        # return gcs_output_prefix
    else:
        logger.info("새롭게 수집된 기사가 없습니다.")
        return None

async def main():
    """
    기능: 스크립트가 직접 실행될 때 뉴스 수집 파이프라인을 실행하기 위한 메인 함수입니다.
    input: 없음
    output: 없음
    """
    setup_logger()
    
    print("스크립트 직접 실행: 전체 뉴스 수집 파이프라인 (GCS 저장) 시작...")
    saved_dir = await run_collection_pipeline()
    if saved_dir:
        # print(f"\n스크립트 실행 완료. 총 {saved_dir}에 {saved_dir.count('/')}개의 기사가 GCS에 저장되었습니다.")
        print(f"\n스크립트 실행 완료. 데이터가 다음 경로에 저장되었습니다: {saved_dir}")
    else:
        print("\n스크립트 실행 완료. 새롭게 수집된 기사가 없습니다.")

if __name__ == "__main__":
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())