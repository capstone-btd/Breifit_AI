import asyncio
import yaml
import os
import sys
from datetime import datetime
import argparse
import re
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# 모델 디렉토리를 Python 경로에 추가
MODELS_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), 'models')
if MODELS_ROOT not in sys.path:
    sys.path.append(MODELS_ROOT)

from src.collection import COLLECTOR_CLASSES
from src.utils.file_helper import save_json_async, get_output_path, slugify
from src.utils.logger import setup_logger

# 번역기 import (선택적)
try:
    from translation.nllb_translator import NLLBTranslator
    TRANSLATION_AVAILABLE = True
except ImportError as e:
    print(f"번역 모듈 로드 실패: {e}")
    print("번역 기능 없이 실행됩니다.")
    TRANSLATION_AVAILABLE = False

CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')
RAW_DATA_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

# 글로벌 번역기 인스턴스
translator = None

def initialize_translator():
    """
    번역기 초기화 (한 번만 실행)
    """
    global translator
    if TRANSLATION_AVAILABLE and translator is None:
        try:
            print("번역기 초기화 중... (NHNDQ/nllb-finetuned-en2ko)")
            translator = NLLBTranslator()
            model_info = translator.get_model_info()
            print(f"번역기 로드 완료: {model_info['model_name']}")
            print(f"번역 방향: {model_info['source_language']} → {model_info['target_language']}")
            return True
        except Exception as e:
            print(f"번역기 초기화 실패: {e}")
            translator = None
            return False
    return TRANSLATION_AVAILABLE

def preprocess_text_simple(text: str) -> str:
    """
    기능: 정규식을 사용하여 텍스트에서 불필요한 공백, 특수문자, 이메일, URL, 저작권 문구 등을 제거한다.
    input: 원본 텍스트 (str)
    output: 전처리된 텍스트 (str)
    """
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\\/]', '', text)
    text = re.sub(r'[^A-Za-z0-9가-힣\s.,\'"%·-]', '', text) 
    copyright_pattern = r'(저작권자|copyright|ⓒ|©)\s?\(?c\)?\s?\w*|무단\s?(전재|배포|재배포)\s?금지|AI\s?학습\s?및\s?활용\s?금지|All\s?rights\s?reserved'
    text = re.sub(copyright_pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\w\.-]+@[\w\.-]+', '', text)
    text = re.sub(r'\d{4}[/\.]\d{2}[/\.]\d{2}\s\d{2}:\d{2}\s송고', '', text)
    return text.strip()

def load_config(config_path: str) -> dict:
    """
    기능: YAML 설정 파일을 로드한다.
    input: 설정 파일 경로 (str)
    output: 설정 내용이 담긴 딕셔너리 (dict)
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"설정 파일 로드 완료: {config_path}")
        return config
    except FileNotFoundError:
        print(f"오류: 설정 파일({config_path})을 찾을 수 없습니다.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"오류: 설정 파일({config_path})을 파싱하는 중 오류 발생: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"오류: 설정 파일 로드 중 알 수 없는 오류 발생: {e}")
        sys.exit(1)

async def run_collection_for_site(site_name: str, site_config: dict, collection_time_str: str):
    """
    기능: 단일 사이트에 대해 기사 수집, 전처리 및 저장을 수행한다.
    input: 사이트 이름(site_name), 사이트 설정(site_config), 수집 시간(collection_time_str)
    output: 없음
    """
    if site_name not in COLLECTOR_CLASSES:
        print(f"경고: '{site_name}'에 대한 컬렉터를 찾을 수 없습니다. 건너뜁니다.")
        return

    collector_class = COLLECTOR_CLASSES.get(site_name.lower())
    if not collector_class:
        print(f"Error: Collector for site '{site_name}' not found.")
        return

    collector = collector_class()
    
    print(f"\n--- 사이트 시작: {site_name.upper()} ---")

    categories_config = site_config.get('categories')
    if not categories_config or not isinstance(categories_config, dict):
        print(f"경고: '{site_name}'에 대한 카테고리 설정이 없거나 유효하지 않습니다. 건너뜁니다.")
        return

    total_articles_collected_for_site = 0

    for category_display_name, category_path_segment in categories_config.items():
        articles_data = []
        
        if isinstance(category_path_segment, list):
            print(f"카테고리 '{category_display_name.upper()}' (다중 경로) 수집 시작: {category_path_segment}...")
            for path_segment in category_path_segment:
                print(f"  경로 '{path_segment}' 에서 수집 중...")
                articles_from_path = await collector.collect_by_category(category_display_name, path_segment)
                if articles_from_path:
                    articles_data.extend(articles_from_path)
        elif isinstance(category_path_segment, str):
            print(f"카테고리 '{category_display_name.upper()}' 수집 시작 ({category_path_segment})...")
            articles_from_path = await collector.collect_by_category(category_display_name, category_path_segment)
            if articles_from_path:
                articles_data.extend(articles_from_path)
        else:
            print(f"경고: 카테고리 '{category_display_name.upper()}'의 경로 형식이 올바르지 않습니다(문자열 또는 리스트여야 함): {category_path_segment}. 건너뜁니다.")
            continue

        if not articles_data:
            print(f"카테고리 '{category_display_name.upper()}' ({site_name})에서 수집된 기사가 없습니다.")
            continue

        print(f"카테고리 '{category_display_name.upper()}' ({site_name})에서 {len(articles_data)}개의 기사 수집 완료. 전처리 및 파일 저장 시작...")
        
        saved_count_for_category = 0
        save_tasks = []
        for article in articles_data:
            if not article or not article.get('title') or not article.get('url'):
                print(f"경고: 필수 정보(제목 또는 URL)가 없는 기사가 있어 건너뜁니다: {article}")
                continue

            original_article_text = article.get('article_text')
            original_title = article.get('title')
            
            # 원본 텍스트 전처리
            if original_article_text:
                processed_text = preprocess_text_simple(original_article_text)
                article['article_text'] = processed_text
                print(f"  - '{original_title[:30]}' 기사 전처리 완료.")
            else:
                article['article_text'] = ""
            
            # 언어 감지 및 번역 (번역기가 사용 가능한 경우)
            if translator and article.get('article_text'):
                try:
                    # 본문이 영어인지 확인
                    if translator.is_english_text(article['article_text']):
                        print(f"    영어 텍스트 감지 - 한국어로 번역 시작")
                        
                        content_to_translate = article['article_text']
                        
                        print(f"    [검증] 번역기로 전달되는 원문 길이: {len(content_to_translate)}자")
                        print(f"    [검증] 원문 앞부분: {content_to_translate[:150]}...")
                        
                        # 영어 → 한국어 번역
                        translated_content = translator.translate(content_to_translate)
                        
                        # 원본 article_text를 번역된 한국어로 교체
                        article['article_text'] = translated_content
                        
                        print(f"    번역 완료 ({len(content_to_translate)}자 → {len(translated_content)}자)")
                        print(f"    번역 결과: {translated_content[:50]}...")
                    else:
                        print(f"    한국어 텍스트 - 번역 불필요")
                    
                except Exception as e:
                    print(f"    번역 실패: {e}")

            article_title_slug = slugify(article['title'])
            if not article_title_slug:
                url_path_parts = [part for part in article['url'].split('/') if part]
                if url_path_parts:
                    article_title_slug = slugify(url_path_parts[-1])
                    if not article_title_slug and len(url_path_parts) > 1:
                         article_title_slug = slugify(url_path_parts[-2])
            if not article_title_slug:
                article_title_slug = f"untitled-article-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            output_filename = f"{article_title_slug}.json"
            file_path = get_output_path(
                base_dir=RAW_DATA_BASE_DIR,
                site_name=site_name,
                category_name=category_display_name,
                filename=output_filename,
                collection_time_str=collection_time_str
            )
            
            save_tasks.append(save_json_async(article, file_path))
            saved_count_for_category +=1
        
        await asyncio.gather(*save_tasks)
        print(f"카테고리 '{category_display_name.upper()}' ({site_name}): {saved_count_for_category}개 기사 저장 완료.")
        total_articles_collected_for_site += saved_count_for_category

    print(f"--- 사이트 {site_name.upper()} 종료: 총 {total_articles_collected_for_site}개 기사 처리 ---")

async def main():
    """
    기능: 설정 파일을 읽어 기사 수집을 위한 전체 프로세스를 관장하고 실행한다.
    input: 없음
    output: 없음
    """
    # 번역기 초기화
    translation_enabled = initialize_translator()
    if translation_enabled:
        print("✅ 번역 기능이 활성화되었습니다.")3


    else:
        print("ℹ️  번역 기능이 비활성화되어 있습니다.")
    
    config = load_config(CONFIG_FILE_PATH)
    sites_to_crawl = config.get('sites')

    if not sites_to_crawl or not isinstance(sites_to_crawl, dict):
        print("오류: 설정 파일에서 'sites' 정보를 찾을 수 없거나 유효하지 않습니다.")
        return
    
    collection_time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_sites_to_run = sites_to_crawl

    tasks = []
    for site_name, site_config_data in target_sites_to_run.items():
        if not isinstance(site_config_data, dict):
            print(f"경고: '{site_name}' 사이트 설정이 유효하지 않습니다. 건너뜁니다.")
            continue
        tasks.append(run_collection_for_site(site_name, site_config_data, collection_time_str))
    
    await asyncio.gather(*tasks)

    print("\n모든 사이트 수집 작업이 완료되었습니다.")
    
    if translation_enabled:
        print("📊 번역 통계:")
        print(f"   - 번역기 모델: {translator.model_name}")
        print(f"   - 디바이스: {translator.device}")
        print("   - 영어 기사는 한국어로 번역되어 article_text에 저장되었습니다.")

if __name__ == '__main__':
    asyncio.run(main())