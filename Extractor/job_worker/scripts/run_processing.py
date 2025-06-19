import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any
from google.cloud import storage
import io

# 필요한 모듈 임포트
from src.processing.article_grouper import ArticleGrouper
from src.processing.summarizer import Summarizer
from DB.database import get_db
from DB import crud
from src.utils.logger import setup_logger

# 상수 정의 - 프로젝트 루트를 기준으로 재설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARIZATION_MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'summarization')

# GCS 설정
GCS_BUCKET_NAME = "betodi-bucket"
storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET_NAME)

def load_articles_from_gcs(gcs_prefix: str) -> List[Dict[str, Any]]:
    """
    기능: GCS의 특정 경로(prefix)에 있는 모든 JSON 파일을 다운로드하여 내용물을 리스트로 반환합니다.
    input: gcs_prefix (GCS 내의 폴더 경로, 예: 'collected_articles/20250619_100000/')
    output: 기사 데이터 딕셔너리가 담긴 리스트
    """
    all_articles = []
    print(f"GCS에서 기사를 로드합니다: gs://{GCS_BUCKET_NAME}/{gcs_prefix}")
    
    blobs = storage_client.list_blobs(GCS_BUCKET_NAME, prefix=gcs_prefix)
    
    for blob in blobs:
        if blob.name.endswith('.json'):
            try:
                json_data = blob.download_as_text()
                all_articles.append(json.loads(json_data))
            except Exception as e:
                print(f"GCS 파일 다운로드/처리 중 에러 발생 {blob.name}: {e}")

    print(f"총 {len(all_articles)}개의 기사를 GCS에서 로드했습니다.")
    return all_articles

def run_processing_pipeline(gcs_prefix: str):
    """
    기능: GCS의 특정 폴더에서 기사를 로드하여 그룹핑, 요약 후 DB에 저장합니다.
    input: gcs_prefix (수집된 기사들이 들어있는 GCS 폴더 경로)
    output: 없음
    """
    logger = setup_logger()
    logger.info(f"기사 처리 파이프라인 시작... (대상: gs://{GCS_BUCKET_NAME}/{gcs_prefix})")
    
    # 1. GCS에서 기사 데이터 로드
    articles = load_articles_from_gcs(gcs_prefix)
    if not articles:
        logger.info("처리할 기사가 없습니다.")
        return

    processing_start_time = datetime.now()

    # 2. 기사 그룹핑
    grouper = ArticleGrouper()
    # 카테고리별로 기사를 분리하여 그룹핑 수행
    articles_by_category: Dict[str, List[Dict]] = {}
    for article in articles:
        category = article.get('category', '기타')
        if category not in articles_by_category:
            articles_by_category[category] = []
        articles_by_category[category].append(article)
    
    all_groups = []
    all_noise = []
    for category, cat_articles in articles_by_category.items():
        logger.info(f"'{category}' 카테고리 그룹핑 시작 ({len(cat_articles)}개 기사)")
        groups, noise = grouper.group(cat_articles)
        all_groups.extend(groups)
        all_noise.extend(noise)
    
    logger.info(f"전체 그룹핑 완료: {len(all_groups)}개 그룹, {len(all_noise)}개 단일 기사.")

    try:
        # with get_db() as db: 구문을 사용하여 안전하게 DB 세션 관리
        with get_db() as db:
            summarizer = Summarizer(model_path=SUMMARIZATION_MODEL_PATH)

            # --- BUG FIX: 단일 기사 처리 로직 활성화 ---
            # 그룹에 속하지 않은 단일 기사(noise)를 처리합니다.
            for article_data in all_noise:
                title = article_data.get('title', '제목 없음')
                logger.info(f"단일 기사 처리 중: {title[:30]}...")
                
                original_body = article_data.get('body', '')
                # 단일 기사는 이미 번역/전처리되었으므로 바로 요약합니다.
                summarized_body = summarizer.summarize(original_body)
                if not summarized_body:
                    logger.warning(f"  - 요약문 생성 실패. 원본 본문을 사용합니다.")
                    summarized_body = original_body[:1000] # 원본 사용 시 길이 제한
                
                final_article_data = {
                    'title': title,
                    'body': summarized_body,
                    'category': article_data.get('category', '기타'),
                    'image_url': article_data.get('image_url', ''),
                    'source_title': title,
                    'source_url': article_data.get('url'),
                    'press_company': article_data.get('source')
                }
                
                crud.create_single_article(db=db, article_data=final_article_data)

            # 여러 기사를 그룹핑하여 처리하는 부분
            for group in all_groups:
                if not group: continue # 빈 그룹은 건너뛰기
                logger.info(f"{len(group)}개의 기사를 가진 그룹 처리 중...")
                
                # 1. 'body' 필드만 합쳐서 요약할 텍스트를 생성합니다.
                bodies_to_summarize = [
                    article.get('body', '').strip() 
                    for article in group if article.get('body')
                ]
                text_to_summarize = "\n\n".join(bodies_to_summarize)
                
                # 2. 합친 본문을 요약합니다.
                summarized_body = summarizer.summarize(text_to_summarize)
                if not summarized_body:
                    logger.warning(f"  - 그룹 요약문 생성 실패. 그룹 처리를 건너뜁니다.")
                    continue

                # 3. DB에 저장할 대표 기사 데이터를 준비합니다. (URL 포함)
                main_article = group[0]
                representative_article_data = {
                    'title': main_article.get('title'),          # 대표 제목 (첫 기사 제목)
                    'body': summarized_body,                     # 요약된 본문
                    'category': main_article.get('category', '기타'),
                    'image_url': main_article.get('image_url', ''),
                    'source_url': main_article.get('url')        # 대표 URL 추가
                }
                
                # 4. 원본 기사 정보 준비
                source_articles_data = []
                for article in group:
                    source_articles_data.append({
                        # 'article_id'는 crud 함수 내부에서 채워짐
                        'title': article.get('title'),
                        'url': article.get('url'),
                        'press_company': article.get('source')
                    })
                
                # 5. 그룹 기사 및 원본 기사들을 DB에 저장
                crud.create_grouped_article(db=db, 
                                            representative_article_data=representative_article_data,
                                            source_articles_data=source_articles_data)
        
        # 6. 마지막 처리 시간 기록
        logger.info(f"기사 처리 파이프라인 완료. 마지막 처리 시간: {processing_start_time.isoformat()}")

    except Exception as e:
        logger.error(f"기사 처리 파이프라인 중 오류 발생: {e}", exc_info=True)
        # 에러가 발생해도 finally 블록이 없으므로 with 구문이 db.close()를 보장합니다.


if __name__ == "__main__":
    run_processing_pipeline() 