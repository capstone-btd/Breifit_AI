import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any
# from google.cloud import storage
# import io
import subprocess
import tempfile

# 필요한 모듈 임포트
from src.processing.article_grouper import ArticleGrouper
# from src.processing.summarizer import GeminiAPIRefiner
from DB.database import get_db
from src.utils.logger import setup_logger

# 상수 정의
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# GCS_BUCKET_NAME = "betodi-gpu"
# storage_client = storage.Client()
# bucket = storage_client.bucket(GCS_BUCKET_NAME)

class GptOssSummarizer:
    """
    외부 gpt-oss-20b 요약 스크립트를 호출하여 요약을 수행하는 클래스.
    """
    def __init__(self):
        current_script_path = os.path.dirname(os.path.abspath(__file__))
        self.summarization_script_path = os.path.join(current_script_path, 'run_summarization_by_gpt.py')
        if not os.path.exists(self.summarization_script_path):
            raise FileNotFoundError(f"Summarization script not found at: {self.summarization_script_path}")

    def refine_text(self, title: str, body: str) -> str:
        if not body or not body.strip():
            print("Warning: Empty body provided for summarization. Skipping.")
            return ""

        summary = ""
        tmp_file_path = None
        try:
            # 임시 파일에 요약할 본문 내용 저장
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix='.txt') as tmp_file:
                tmp_file.write(body)
                tmp_file_path = tmp_file.name

            command = [
                sys.executable,  # 현재 파이썬 인터프리터 사용
                self.summarization_script_path,
                '--text_file',
                tmp_file_path
            ]
            
            # [수정] 자식 프로세스를 위한 환경 변수 설정
            # 부모 프로세스의 환경을 복사한 뒤, 필요한 HF 관련 변수를 덮어씁니다.
            # 이렇게 해야 자식 프로세스가 올바른 캐시 경로를 사용합니다.
            child_env = os.environ.copy()
            child_env['HF_HOME'] = '/home/bobo9245/projects/hf_cache'
            child_env['HF_HUB_ENABLE_HF_TRANSFER'] = '1'

            print(f"Calling GPT-OSS summarization script for title: {title[:30]}...")
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                check=True,
                env=child_env  # 생성한 환경 변수를 자식 프로세스에 전달
            )

            # [수정된 최종 로직]
            # 이제 요약 스크립트가 순수한 결과물만 stdout으로 보내므로, 그대로 사용합니다.
            summary = result.stdout
            
            if not summary or not summary.strip():
                 print(f"Warning: Summarization script returned an empty result for title: {title[:30]}")
                 print(f"Stderr from script:\n{result.stderr}") # 디버깅을 위해 stderr 출력

        except subprocess.CalledProcessError as e:
            print(f"Error calling summarization script for title '{title[:30]}': {e}")
            print(f"Stdout from script on error:\n{e.stdout}")
            print(f"Stderr from script on error:\n{e.stderr}")
            summary = "" # 오류 발생 시 요약문은 비워둠
        except Exception as e:
            print(f"An unexpected error occurred during summarization for title '{title[:30]}': {e}")
            summary = ""
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)

        return summary.strip()

# def load_articles_from_gcs(gcs_prefix: str) -> List[Dict[str, Any]]:
#     """
#     기능: GCS의 특정 경로(prefix)에 있는 모든 JSON 파일을 다운로드하여 내용물을 리스트로 반환합니다.
#     """
#     all_articles = []
#     print(f"GCS에서 기사를 로드합니다: gs://{GCS_BUCKET_NAME}/{gcs_prefix}")
#     
#     blobs = storage_client.list_blobs(GCS_BUCKET_NAME, prefix=gcs_prefix)
#     
#     for blob in blobs:
#         if blob.name.endswith('.json'):
#             try:
#                 json_data = blob.download_as_text(encoding='utf-8')
#                 all_articles.append(json.loads(json_data))
#             except Exception as e:
#                 print(f"GCS 파일 다운로드/처리 중 에러 발생 {blob.name}: {e}")
#
#     print(f"총 {len(all_articles)}개의 기사를 GCS에서 로드했습니다.")
#     return all_articles

def load_articles_from_local(local_path_prefix: str) -> List[Dict[str, Any]]:
    """
    기능: 로컬의 특정 경로에 있는 모든 JSON 파일을 읽어 내용물을 리스트로 반환합니다.
    """
    all_articles = []
    print(f"로컬 경로에서 기사를 로드합니다: {local_path_prefix}")
    
    if not os.path.isdir(local_path_prefix):
        print(f"오류: 제공된 경로가 디렉터리가 아닙니다: {local_path_prefix}")
        return []

    for root, _, files in os.walk(local_path_prefix):
        for filename in files:
            if filename.endswith('.json'):
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        all_articles.append(json.load(f))
                except Exception as e:
                    print(f"로컬 파일 읽기/처리 중 에러 발생 {file_path}: {e}")

    print(f"총 {len(all_articles)}개의 기사를 로컬에서 로드했습니다.")
    return all_articles

def run_processing_for_wc_pipeline(local_data_path: str):
    """
    기능: 로컬의 특정 폴더에서 기사를 로드하여 그룹핑, 요약 후 DB에 저장합니다.
    ('기타' 카테고리 제외)
    input: local_data_path (수집된 기사들이 들어있는 로컬 폴더 경로)
    output: 없음
    """
    from DB import crud

    logger = setup_logger()
    logger.info(f"WordCloud용 기사 처리 파이프라인 시작 (그룹핑 포함)... (대상: {local_data_path})")
    
    all_articles = load_articles_from_local(local_data_path)
    if not all_articles:
        logger.info("처리할 기사가 없습니다.")
        return

    # '기타' 카테고리 기사를 처리에서 제외
    articles_to_process = [
        article for article in all_articles 
        if article.get('category', '기타') != '기타'
    ]
    
    if not articles_to_process:
        logger.info("'기타' 카테고리를 제외하니 처리할 기사가 없습니다.")
        return
        
    logger.info(f"'기타' 카테고리 제외 후 {len(articles_to_process)}개 기사 처리 시작...")
    
    processing_start_time = datetime.now()

    # 기사 그룹핑
    grouper = ArticleGrouper()
    articles_by_category: Dict[str, List[Dict]] = {}
    for article in articles_to_process:
        category = article.get('category')
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
        with get_db() as db:
            summarizer = GptOssSummarizer()

            # 단일 기사(noise) 처리
            for article_data in all_noise:
                title = article_data.get('title', '제목 없음')
                logger.info(f"단일 기사 처리 중: {title[:30]}...")
                
                body_content = article_data.get('body', '')
                if isinstance(body_content, list):
                    original_body = "\n".join(body_content)
                else:
                    original_body = body_content
                
                summarized_body = summarizer.refine_text(title=title, body=original_body) 
                if not summarized_body:
                    logger.warning(f"  - 요약문 생성 실패. 원본 본문을 사용합니다.")
                    summarized_body = original_body[:1000]
                
                final_article_data = {
                    'title': title,
                    'body': summarized_body,
                    'category': article_data.get('category', '기타'),
                    'image_url': article_data.get('image_url', ''),
                    'source_title': title,
                    'source_url': article_data.get('url'),
                    'press_company': '네이버뉴스'
                }
                
                crud.create_single_article(db=db, article_data=final_article_data)

            # 그룹 기사 처리
            for group in all_groups:
                if not group: continue
                logger.info(f"{len(group)}개의 기사를 가진 그룹 처리 중...")
                
                bodies_to_summarize = [
                    article.get('body', '').strip() 
                    for article in group if article.get('body')
                ]
                text_to_summarize = "\n\n".join(bodies_to_summarize)
                
                main_article_title = group[0].get('title', '그룹 기사')
                summarized_body = summarizer.refine_text(title=main_article_title, body=text_to_summarize)
                if not summarized_body:
                    logger.warning(f"  - 그룹 요약문 생성 실패. 그룹 처리를 건너뜁니다.")
                    continue

                main_article = group[0]
                representative_article_data = {
                    'title': main_article_title,
                    'body': summarized_body,
                    'category': main_article.get('category', '기타'),
                    'image_url': main_article.get('image_url', ''),
                    'source_url': main_article.get('url')
                }
                
                source_articles_data = []
                for article in group:
                    source_articles_data.append({
                        'title': article.get('title'),
                        'url': article.get('url'),
                        'press_company': '네이버뉴스'
                    })
                
                crud.create_grouped_article(db=db, 
                                            representative_article_data=representative_article_data,
                                            source_articles_data=source_articles_data)
        
        logger.info(f"기사 처리 파이프라인 완료. 마지막 처리 시간: {processing_start_time.isoformat()}")

    except Exception as e:
        logger.error(f"기사 처리 파이프라인 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    print("이 스크립트는 외부(예: 파이프라인 조정자)에서 local_data_path 인자와 함께 호출되어야 합니다.") 