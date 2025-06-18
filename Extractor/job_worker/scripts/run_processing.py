import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any

# 프로젝트 루트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(current_dir)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 필요한 모듈 임포트
from src.processing.article_grouper import ArticleGrouper
from src.processing.summarizer import Summarizer
from DB.database import SessionLocal
from DB import crud
from src.utils.logger import setup_logger

# 상수 정의
COLLECTED_ARTICLES_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'collected_articles')
PROCESSED_TIME_FILE = os.path.join(COLLECTED_ARTICLES_BASE_DIR, 'last_processed_time.txt')
# 요약 모델 경로
SUMMARIZATION_MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'summarization')

def get_last_processed_time() -> datetime | None:
    """
    기능: 마지막으로 기사 처리를 실행한 시간을 파일에서 읽어옵니다. 이 시간은 새로운 기사만 처리하기 위한 기준점이 됩니다.
    input: 없음
    output: 마지막 처리 시간을 나타내는 datetime 객체 또는 파일이 없을 경우 None
    """
    if not os.path.exists(PROCESSED_TIME_FILE):
        return None
    with open(PROCESSED_TIME_FILE, 'r') as f:
        timestamp_str = f.read().strip()
        try:
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return None

def set_last_processed_time(process_time: datetime):
    """
    기능: 기사 처리를 완료한 현재 시간을 파일에 기록합니다.
    input: process_time (현재 처리 시간의 datetime 객체)
    output: 없음
    """
    os.makedirs(os.path.dirname(PROCESSED_TIME_FILE), exist_ok=True)
    with open(PROCESSED_TIME_FILE, 'w') as f:
        f.write(process_time.isoformat())

def load_new_articles() -> List[Dict[str, Any]]:
    """
    기능: 마지막으로 처리한 시간 이후에 수집된 모든 새로운 기사 파일(JSON)을 불러옵니다.
    input: 없음
    output: 새로운 기사 데이터 딕셔너리가 담긴 리스트
    """
    last_processed_time = get_last_processed_time()
    all_new_articles = []
    
    if not os.path.exists(COLLECTED_ARTICLES_BASE_DIR):
        print("수집된 기사 폴더가 존재하지 않습니다.")
        return []

    for dirpath, _, filenames in os.walk(COLLECTED_ARTICLES_BASE_DIR):
        for filename in filenames:
            if filename.endswith('.json'):
                file_path = os.path.join(dirpath, filename)
                try:
                    # 파일 수정 시간을 기준으로 새로운 파일인지 판단
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if last_processed_time is None or file_mod_time > last_processed_time:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            all_new_articles.append(json.load(f))
                except Exception as e:
                    print(f"파일 로딩/처리 중 에러 발생 {file_path}: {e}")
    
    print(f"마지막 처리 시간({last_processed_time}) 이후 수집된 {len(all_new_articles)}개의 새 기사를 로드했습니다.")
    return all_new_articles

def run_processing_pipeline():
    """
    기능: 전체 기사 처리 파이프라인을 실행합니다. 로컬의 새 기사를 로드하여 카테고리별로 그룹핑하고, 요약한 뒤, 최종 결과를 데이터베이스에 저장합니다.
    input: 없음
    output: 없음
    """
    logger = setup_logger()
    logger.info("기사 처리 파이프라인 시작...")
    
    # 1. 새로운 기사 데이터 로드
    articles = load_new_articles()
    if not articles:
        logger.info("처리할 새로운 기사가 없습니다.")
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

    db = SessionLocal()
    try:
        summarizer = Summarizer(model_path=SUMMARIZATION_MODEL_PATH)

        # # 단일 기사 처리하는 부분
        # for article_data in all_noise:
        #     title = article_data.get('title', '제목 없음')
        #     logger.info(f"단일 기사 처리 중: {title[:30]}...")
            
        #     original_body = article_data.get('body', '')
        #     summarized_body = summarizer.summarize(original_body)
        #     if not summarized_body:
        #         logger.warning(f"  - 요약문 생성 실패. 원본 본문을 사용합니다.")
        #         summarized_body = original_body[:500] # 원본 사용 시 길이 제한
            
        #     final_article_data = {
        #         'title': title,
        #         'body': summarized_body,
        #         'category': article_data.get('category', '기타'),
        #         'image_url': article_data.get('image_url', ''),
        #         'source_title': title,
        #         'source_url': article_data.get('url'),
        #         'press_company': article_data.get('source')
        #     }
            
        #     crud.create_single_article(db=db, article_data=final_article_data)

        # 여러 기사를 그룹핑하여 처리하는 부분
        for group in all_groups:
            if not group: continue # 빈 그룹은 건너뛰기
            logger.info(f"{len(group)}개의 기사를 가진 그룹 처리 중...")
            
            # 5-1. 대표 기사 선정 및 정보 취합 (첫 번째 기사 기준)
            main_article = group[0]
            
            # 5-2. 요약을 위해 모든 기사의 제목과 본문 합치기
            text_to_summarize = ""
            for article in group:
                text_to_summarize += f"제목: {article.get('title', '')}\n본문: {article.get('body', '')}\n\n"
            
            # 5-3. 합친 내용 요약
            summarized_body = summarizer.summarize(text_to_summarize)
            if not summarized_body:
                logger.warning(f"  - 그룹 요약문 생성 실패. 그룹 처리를 건너뜁니다.")
                continue

            # 5-4. DB 저장을 위한 대표 기사 데이터 준비
            representative_article_data = {
                'title': main_article.get('title'), # 대표 제목
                'body': summarized_body, # 요약된 본문
                'category': main_article.get('category', '기타'),
                'image_url': main_article.get('image_url', '')
            }
            
            # 5-5. 원본 기사 정보 준비
            source_articles_data = []
            for article in group:
                source_articles_data.append({
                    # 'article_id'는 crud 함수 내부에서 채워짐
                    'title': article.get('title'),
                    'url': article.get('url'),
                    'press_company': article.get('source')
                })
            
            # 5-6. 그룹 기사 및 원본 기사들을 DB에 저장
            crud.create_grouped_article(db=db, 
                                        representative_article_data=representative_article_data,
                                        source_articles_data=source_articles_data)
        
        # 6. 마지막 처리 시간 기록
        set_last_processed_time(processing_start_time)
        logger.info(f"기사 처리 파이프라인 완료. 마지막 처리 시간: {processing_start_time.isoformat()}")

    except Exception as e:
        logger.error(f"기사 처리 파이프라인 중 오류 발생: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    run_processing_pipeline() 