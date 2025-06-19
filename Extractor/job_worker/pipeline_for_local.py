# Cursor 통해서 작성한 코드입니다. run_full_pipeline.py 코드를 참고하여 작성했습니다.

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any
from slugify import slugify

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from scripts.run_collection import run_collection_pipeline

from scripts.run_processing import load_new_articles, set_last_processed_time
from src.processing.article_grouper import ArticleGrouper
from src.processing.summarizer import Summarizer
from src.utils.logger import setup_logger

PROCESSED_ARTICLES_BASE_DIR = os.path.join(project_root, 'data', 'processed_articles')
SUMMARIZATION_MODEL_PATH = os.path.join(project_root, 'models', 'summarization')

def save_to_local_json(data: Dict, file_path: str):
    """Helper function to save dictionary data to a JSON file."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"  - Successfully saved processed data to: {file_path}")
    except Exception as e:
        print(f"  - Error saving JSON to {file_path}: {e}")

def run_local_processing_pipeline(logger):
    """
    Processes collected articles and saves the final output to local JSON files
    instead of a database.
    """
    logger.info("[LOCAL PIPELINE] Starting Local Processing Stage...")

    # 1. Load new articles from `data/collected_articles`
    articles = load_new_articles()
    if not articles:
        logger.info("[LOCAL PIPELINE] No new articles to process.")
        return

    processing_start_time = datetime.now()
    output_dir_timestamp = processing_start_time.strftime("%Y%m%d_%H%M%S")
    
    # 2. Group articles by category
    grouper = ArticleGrouper()
    articles_by_category: Dict[str, List[Dict]] = {}
    for article in articles:
        category = article.get('category', '기타')
        articles_by_category.setdefault(category, []).append(article)
    
    all_groups = []
    all_noise = []
    for category, cat_articles in articles_by_category.items():
        logger.info(f"'{category}' 카테고리 그룹핑 시작 ({len(cat_articles)}개 기사)")
        groups, noise = grouper.group(cat_articles)
        all_groups.extend(groups)
        all_noise.extend(noise)
    
    logger.info(f"전체 그룹핑 완료: {len(all_groups)}개 그룹, {len(all_noise)}개 단일 기사.")

    # 3. Summarize and save to local files
    summarizer = Summarizer(model_path=SUMMARIZATION_MODEL_PATH)

    # Process single (noise) articles
    logger.info("--- Processing Single Articles ---")
    for i, article_data in enumerate(all_noise):
        title = article_data.get('title', '제목 없음')
        logger.info(f"Processing single article ({i+1}/{len(all_noise)}): {title[:30]}...")
        
        summarized_body = summarizer.summarize(article_data.get('body', ''))
        
        final_data = {
            'type': 'single_article',
            'processed_at': processing_start_time.isoformat(),
            'title': title,
            'summarized_body': summarized_body or article_data.get('body', '')[:1000],
            'category': article_data.get('category', '기타'),
            'image_url': article_data.get('image_url', ''),
            'source_url': article_data.get('url'),
            'source_press': article_data.get('source')
        }
        
        # Create directory structure based on press company and category
        press_company = slugify(article_data.get('source', 'unknown-press'), allow_unicode=True)
        category = slugify(article_data.get('category', 'etc'), allow_unicode=True)
        filename = f"single_{i+1}_{slugify(title[:20], allow_unicode=True)}.json"
        
        output_path = os.path.join(PROCESSED_ARTICLES_BASE_DIR, output_dir_timestamp, press_company, category, filename)
        save_to_local_json(final_data, output_path)

    # Process grouped articles
    logger.info("--- Processing Grouped Articles ---")
    for i, group in enumerate(all_groups):
        if not group: continue
        logger.info(f"Processing group ({i+1}/{len(all_groups)}) with {len(group)} articles...")
        
        main_article = group[0]
        text_to_summarize = "".join([f"제목: {a.get('title', '')}\n본문: {a.get('body', '')}\n\n" for a in group])
        
        summarized_body = summarizer.summarize(text_to_summarize)
        
        final_data = {
            'type': 'grouped_article',
            'processed_at': processing_start_time.isoformat(),
            'representative_title': main_article.get('title'),
            'summarized_body': summarized_body or "요약 생성 실패",
            'category': main_article.get('category', '기타'),
            'image_url': main_article.get('image_url', ''),
            'article_count': len(group),
            'source_articles': [
                {'title': a.get('title'), 'url': a.get('url'), 'press_company': a.get('source')}
                for a in group
            ]
        }

        # Create directory structure based on the representative article's info
        main_article_info = group[0]
        press_company = slugify(main_article_info.get('source', 'unknown-press'), allow_unicode=True)
        category = slugify(main_article_info.get('category', 'etc'), allow_unicode=True)
        filename = f"group_{i+1}_{slugify(main_article_info.get('title', 'UNTITLED')[:20], allow_unicode=True)}.json"

        output_path = os.path.join(PROCESSED_ARTICLES_BASE_DIR, output_dir_timestamp, press_company, category, filename)
        save_to_local_json(final_data, output_path)

    # 4. Update the last processed time to avoid re-processing
    set_last_processed_time(processing_start_time)
    logger.info(f"[LOCAL PIPELINE] Local processing finished. Last processed time updated.")


async def main():
    """
    Main function to run the entire local pipeline.
    """
    logger = setup_logger()
    logger.info("==============================================")
    logger.info("======= Local Full Pipeline Job Started =======")
    logger.info("==============================================")

    try:
        # --- Stage 1: Data Collection ---
        logger.info("[PIPELINE] Starting Stage 1: Data Collection")
        await run_collection_pipeline()
        logger.info("[PIPELINE] Finished Stage 1: Data Collection")

        # --- Stage 2: Local Data Processing ---
        logger.info("[PIPELINE] Starting Stage 2: Local Data Processing")
        run_local_processing_pipeline(logger)
        logger.info("[PIPELINE] Finished Stage 2: Local Data Processing")

        logger.info("======= Local Full Pipeline Job Succeeded =======")

    except Exception as e:
        logger.error(f"[PIPELINE] An unhandled error occurred in the local pipeline: {e}", exc_info=True)
        logger.error("======= Local Full Pipeline Job Failed =======")
        raise

if __name__ == "__main__":
    # To run this script, simply execute `python pipeline_for_local.py` in your terminal.
    asyncio.run(main()) 