# 이 스크립트를 통해 기사를 크롤링합니다.
# 이를 통해서 크롤링을 진행하려고 한다면, 이걸 그대로 사용하는 것이 아니라
# news_sites.yaml 파일을 수정해야 합니다. 코드 수정하지 마세요


import asyncio
import yaml # PyYAML 필요
import os
import sys
from datetime import datetime
import argparse

# 언어 감지 및 번역을 위한 라이브러리 추가
try:
    from langdetect import detect as detect_language, LangDetectException
except ImportError:
    print("langdetect 라이브러리가 설치되지 않았습니다. 'pip install langdetect'로 설치해주세요.")
    sys.exit(1)

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
except ImportError:
    print("transformers 또는 torch 라이브러리가 설치되지 않았습니다. 'pip install transformers torch sentencepiece'로 설치해주세요.")
    sys.exit(1)


# 프로젝트 루트 경로를 sys.path에 추가 (src 폴더의 모듈을 임포트하기 위함)
# 이 스크립트(run_collection.py)가 scripts/ 폴더에 있다고 가정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.collection import COLLECTOR_CLASSES
from src.utils.file_helper import save_json_async, get_output_path, slugify
from src.utils.logger import setup_logger
# from src.utils.database import get_db_session_context, init_db # 현재 사용되지 않으므로 주석 처리

CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')
RAW_DATA_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

# 번역 함수 정의 (NLLB 모델 사용)
def translate_english_to_korean_nllb(text: str, tokenizer, model, device, max_length: int = 512) -> str | None:
    """NLLB 모델을 사용하여 영어 텍스트를 한국어로 번역합니다."""
    if not text or not text.strip():
        return None
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length).to(device)
        translated_tokens = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.lang_code_to_id["kor_Hang"],
            max_length=max_length + 50 # 원본보다 약간 길게 설정 가능
        )
        korean_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        return korean_text
    except Exception as e:
        print(f"번역 중 오류 발생: {e}")
        return None

def load_config(config_path: str) -> dict:
    """YAML 설정 파일을 로드합니다."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"설정 파일 로드 완료: {config_path}")
        return config
    except FileNotFoundError:
        print(f"오류: 설정 파일({config_path})을 찾을 수 없습니다.")
        sys.exit(1) # 오류 발생 시 프로그램 종료
    except yaml.YAMLError as e:
        print(f"오류: 설정 파일({config_path})을 파싱하는 중 오류 발생: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"오류: 설정 파일 로드 중 알 수 없는 오류 발생: {e}")
        sys.exit(1)

async def run_collection_for_site(site_name: str, site_config: dict, collection_time_str: str, 
                                  translator_tokenizer=None, translator_model=None, translator_device=None): # 번역기 관련 파라미터 추가
    """특정 사이트에 대해 기사 수집을 실행합니다."""
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
        # print(f"카테고리 '{category_display_name.upper()}' 수집 시작 ({category_path_segment})...") # 원본 로그 위치 변경
        
        articles_data = [] # 최종적으로 모든 경로의 기사를 담을 리스트
        
        if isinstance(category_path_segment, list):
            print(f"카테고리 '{category_display_name.upper()}' (다중 경로) 수집 시작: {category_path_segment}...")
            for path_segment in category_path_segment:
                print(f"  경로 '{path_segment}' 에서 수집 중...")
                # 각 경로에 대해 category_display_name (예: 'technology')과 실제 경로(path_segment)를 전달
                articles_from_path = await collector.collect_by_category(category_display_name, path_segment)
                if articles_from_path:
                    articles_data.extend(articles_from_path)
        elif isinstance(category_path_segment, str): # 단일 문자열 경로인 경우
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

        print(f"카테고리 '{category_display_name.upper()}' ({site_name})에서 {len(articles_data)}개의 기사 수집 완료. 파일 저장 시작...")
        
        saved_count_for_category = 0
        save_tasks = []
        for article in articles_data:
            if not article or not article.get('title') or not article.get('url'):
                print(f"경고: 필수 정보(제목 또는 URL)가 없는 기사가 있어 건너뜁니다: {article}")
                continue

            # 언어 감지 및 번역 (article_text가 있는 경우)
            original_article_text = article.get('article_text')
            if original_article_text and translator_tokenizer and translator_model and translator_device:
                try:
                    detected_lang = detect_language(original_article_text)
                    if detected_lang == 'en':
                        print(f"'{article.get('title', '알 수 없는 제목')}' 기사 (영어) 번역 시도...")
                        translated_text = await asyncio.to_thread(
                            translate_english_to_korean_nllb,
                            original_article_text,
                            translator_tokenizer,
                            translator_model,
                            translator_device
                        )
                        if translated_text:
                            article['article_text_ko'] = translated_text
                            article['is_translated'] = True
                            article['original_lang'] = 'en'
                            print(f"'{article.get('title', '알 수 없는 제목')}' 기사 번역 완료.")
                        else:
                            print(f"'{article.get('title', '알 수 없는 제목')}' 기사 번역 실패.")
                            article['is_translated'] = False
                            article['original_lang'] = 'en' # 감지는 했으므로 기록
                    else:
                        article['original_lang'] = detected_lang
                        article['is_translated'] = False

                except LangDetectException:
                    print(f"'{article.get('title', '알 수 없는 제목')}' 기사의 언어를 감지할 수 없습니다.")
                    article['original_lang'] = 'unknown'
                    article['is_translated'] = False
                except Exception as e:
                    print(f"'{article.get('title', '알 수 없는 제목')}' 기사 처리 중 오류: {e}")
                    article['original_lang'] = 'error'
                    article['is_translated'] = False


            article_title_slug = slugify(article['title'])
            if not article_title_slug:
                url_path_parts = [part for part in article['url'].split('/') if part]
                if url_path_parts:
                    article_title_slug = slugify(url_path_parts[-1]) # URL의 마지막 경로 세그먼트
                    if not article_title_slug and len(url_path_parts) > 1:
                         article_title_slug = slugify(url_path_parts[-2]) # 그 앞의 세그먼트
            if not article_title_slug: # 그래도 슬러그를 만들 수 없으면 고유 ID 기반 파일명
                article_title_slug = f"untitled-article-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            output_filename = f"{article_title_slug}.json"
            file_path = get_output_path(
                base_dir=RAW_DATA_BASE_DIR,
                site_name=collection_time_str,
                category_name=category_display_name,
                filename=output_filename
            )
            
            save_tasks.append(save_json_async(article, file_path))
            saved_count_for_category +=1
        
        await asyncio.gather(*save_tasks)
        print(f"카테고리 '{category_display_name.upper()}' ({site_name}): {saved_count_for_category}개 기사 저장 완료.")
        total_articles_collected_for_site += saved_count_for_category

    print(f"--- 사이트 {site_name.upper()} 종료: 총 {total_articles_collected_for_site}개 기사 처리 ---")

async def main():
    config = load_config(CONFIG_FILE_PATH)
    sites_to_crawl = config.get('sites')

    if not sites_to_crawl or not isinstance(sites_to_crawl, dict):
        print("오류: 설정 파일에서 'sites' 정보를 찾을 수 없거나 유효하지 않습니다.")
        return
    
    # 번역 모델 및 토크나이저 로드
    translator_tokenizer = None
    translator_model = None
    translator_device = None
    try:
        # 모델명 변경 가능 (예: "facebook/nllb-200-1.3B" 등)
        model_name = "facebook/nllb-200-distilled-600M" 
        print(f"번역 모델 로드 중: {model_name}...")
        translator_tokenizer = AutoTokenizer.from_pretrained(model_name, src_lang="eng_Latn")
        translator_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        translator_device = "cuda" if torch.cuda.is_available() else "cpu"
        translator_model.to(translator_device)
        print(f"번역 모델 로드 완료. 사용 장치: {translator_device}")
    except Exception as e:
        print(f"번역 모델 로드 실패: {e}. 번역 기능 없이 진행합니다.")
        translator_tokenizer = None
        translator_model = None
        translator_device = None

    collection_time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_sites_to_run = sites_to_crawl

    tasks = []
    for site_name, site_config_data in target_sites_to_run.items():
        if not isinstance(site_config_data, dict):
            print(f"경고: '{site_name}' 사이트 설정이 유효하지 않습니다. 건너뜁니다.")
            continue
        # 각 사이트 수집 작업에 로드된 번역기 객체들 전달
        tasks.append(run_collection_for_site(site_name, site_config_data, collection_time_str, 
                                             translator_tokenizer, translator_model, translator_device))
    
    await asyncio.gather(*tasks) # 여러 사이트 동시에 실행

    print("\n모든 사이트 수집 작업이 완료되었습니다.")

if __name__ == '__main__':
    asyncio.run(main()) 