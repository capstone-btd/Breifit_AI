import asyncio
import yaml
import os
import sys
from datetime import datetime
import logging
import json
from pathlib import Path
from typing import Dict, Any
from slugify import slugify as python_slugify

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

def get_output_path(base_dir: str, site_name: str, category_name: str, filename: str, collection_time_str: str) -> str:
    """기사 저장 경로 생성"""
    path = os.path.join(base_dir, collection_time_str, site_name, category_name)
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

def preprocess_article(article: dict) -> dict:
    """기사 데이터 전처리"""
    if not article or not isinstance(article, dict):
        return None

    if not article.get('title') or not article.get('url'):
        print(f"경고: 필수 정보(제목 또는 URL)가 없는 기사가 있어 건너뜁니다: {article}")
        return None

    original_article_text = article.get('article_text', '')
    if original_article_text:
        processed_text = preprocess_text_simple(original_article_text)
        article['article_text'] = processed_text
        print(f"  - '{article['title'][:30]}' 기사 전처리 완료.")
    else:
        article['article_text'] = ""

    if len(article.get('article_text', '').strip()) < 30:
        print(f"  - 경고: 최종 기사 내용이 30자 미만이라 저장하지 않습니다. (제목: '{article['title'][:30]}...')")
        return None

    # 번역 처리 (영어 기사인 경우)
    current_translator = get_translator()
    if current_translator and article.get('article_text'):
        # 영어 텍스트인지 확인 (간단한 방법: 영어 문자 비율 체크)
        english_chars = sum(1 for c in article['article_text'] if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in article['article_text'] if c.isalpha())
        
        if total_chars > 0 and english_chars / total_chars > 0.7:  # 70% 이상이 영어인 경우
            try:
                # 기사 본문 번역
                translated_text = current_translator.translate(article['article_text'])
                article['article_text'] = translated_text
                print(f"  - '{article['title'][:30]}' 기사 본문 번역 완료.")
                
                # 제목 번역
                translated_title = current_translator.translate_single(article['title'])
                article['title'] = translated_title
                print(f"  - '{article['title'][:30]}' 제목 번역 완료.")
                
            except Exception as e:
                print(f"  - 경고: 번역 중 오류 발생: {e}")

    return article

async def run_collection_for_site(site_name: str, site_config: dict, collection_time_str: str, raw_data_base_dir: str):
    """특정 언론사의 모든 카테고리에서 기사 수집"""
    print(f"\n[run_collection] {site_name.upper()} 수집 시작...")
    
    collector = get_collector_for_site(site_name, site_config)
    if not collector:
        return

    categories_config = site_config.get('categories', {})
    if not categories_config:
        print(f"경고: {site_name}에 대한 카테고리 설정이 없습니다. 건너뜁니다.")
        return

    category_tasks = []
    for category_display_name, category_path_segment in categories_config.items():
        if isinstance(category_path_segment, list):
            for path_segment in category_path_segment:
                category_tasks.append(collector.collect_by_category(category_display_name, path_segment))
        elif isinstance(category_path_segment, str):
            category_tasks.append(collector.collect_by_category(category_display_name, category_path_segment))

    if not category_tasks:
        print(f"경고: {site_name}에 대한 유효한 카테고리 설정이 없습니다.")
        return

    category_results = await asyncio.gather(*category_tasks, return_exceptions=True)
    
    for result in category_results:
        if isinstance(result, Exception):
            print(f"카테고리 수집 중 오류 발생: {result}")
            continue
            
        articles_data = result
        if not articles_data:
            continue

        category_display_name = articles_data[0].get('category', 'etc') if articles_data else 'etc'
        print(f"카테고리 '{category_display_name}' ({site_name})에서 {len(articles_data)}개 기사 수집 완료. 전처리 및 파일 저장 시작...")
        
        save_tasks = []
        for article in articles_data:
            if article and isinstance(article, dict):
                processed_article = preprocess_article(article)
                if processed_article:
                    article_title_slug = python_slugify(processed_article['title'])
                    if not article_title_slug:
                        article_title_slug = f"untitled-article-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    
                    output_filename = f"{article_title_slug}.json"
                    file_path = get_output_path(
                        raw_data_base_dir,
                        site_name,
                        category_display_name,
                        output_filename,
                        collection_time_str
                    )
                    save_tasks.append(save_json_async(processed_article, file_path))
        
        if save_tasks:
            await asyncio.gather(*save_tasks, return_exceptions=True)

async def run_collection_pipeline(raw_data_base_dir: str):
    """
    전체 뉴스 수집 파이프라인을 실행하는 메인 함수. main.py에서 호출됩니다.
    """
    print("\n[run_collection] 전체 뉴스 수집 파이프라인 시작...")
    config = load_config(CONFIG_FILE_PATH)
    if not config:
        print("[run_collection] 에러: 설정 파일을 찾을 수 없어 파이프라인을 중단합니다.")
        return

    collection_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[run_collection] 뉴스 수집 시작 시간: {collection_time_str}")

    site_tasks = [
        run_collection_for_site(site_name, site_config, collection_time_str, raw_data_base_dir)
        for site_name, site_config in config['sites'].items()
    ]
    await asyncio.gather(*site_tasks)

    print(f"\n[run_collection] 모든 사이트의 뉴스 수집 완료: {collection_time_str}")

if __name__ == "__main__":
    setup_logger()
    logging.info("="*50)
    logging.info("뉴스 기사 수집 스크립트 시작")
    asyncio.run(run_collection_pipeline(RAW_DATA_BASE_DIR))
    logging.info("뉴스 기사 수집 스크립트 종료")
    logging.info("="*50 + "\n")