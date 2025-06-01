# 이 스크립트를 통해 기사를 크롤링합니다.
# 이를 통해서 크롤링을 진행하려고 한다면, 이걸 그대로 사용하는 것이 아니라
# news_sites.yaml 파일을 수정해야 합니다. 코드 수정하지 마세요


import asyncio
import yaml # PyYAML 필요
import os
import sys
from datetime import datetime
import argparse

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

async def run_collection_for_site(site_name: str, site_config: dict):
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
        print(f"카테고리 '{category_display_name.upper()}' 수집 시작 ({category_path_segment})...")
        
        articles_data = await collector.collect_by_category(category_display_name, category_path_segment)

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
                site_name=site_name,
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
    
    target_sites_to_run = sites_to_crawl

    for site_name, site_config_data in target_sites_to_run.items():
        if not isinstance(site_config_data, dict):
            print(f"경고: '{site_name}' 사이트 설정이 유효하지 않습니다. 건너뜁니다.")
            continue
        await run_collection_for_site(site_name, site_config_data)

    print("\n모든 사이트 수집 작업이 완료되었습니다.")

if __name__ == '__main__':
    asyncio.run(main()) 