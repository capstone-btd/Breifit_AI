import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any
# from google.cloud import storage # GCS 관련 import 주석 처리
# import io # GCS 관련 import 주석 처리
import subprocess
import tempfile
import re
import textwrap # 텍스트 줄바꿈을 위해 임포트
import logging

# 필요한 모듈 임포트
from src.processing.article_grouper import ArticleGrouper
# from src.processing.summarizer import GeminiAPIRefiner # Gemini API 대신 GPT-OSS 사용
from DB.database import get_db
from src.utils.logger import setup_logger
from DB import crud # crud 모듈 임포트

# 상수 정의 - 프로젝트 루트를 기준으로 재설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# SUMMARIZATION_MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'kobart-sum', 'final') # 로컬 모델 경로 불필요

# GCS 설정 주석 처리
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
#     input: gcs_prefix (GCS 내의 폴더 경로, 예: 'collected_articles/20250619_100000/')
#     output: 기사 데이터 딕셔너리가 담긴 리스트
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
    input: local_path_prefix (로컬 내의 폴더 경로, 예: '/path/to/project/Data/collected_articles/20250619_100000/')
    output: 기사 데이터 딕셔너리가 담긴 리스트
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

def run_processing_pipeline(
    local_data_path: str
) -> None:
    """전체 기사 처리 파이프라인을 실행합니다."""
    logger = setup_logger('processing_pipeline')
    
    # 1. 로컬에서 기사 로드
    logger.info(f"로컬에서 기사 로드 중: {local_data_path}")
    articles = load_articles_from_local(local_data_path)
    if not articles:
        logger.warning("처리할 기사가 없습니다.")
        return

    # 2. 기사 그룹화
    logger.info(f"총 {len(articles)}개의 기사 그룹화 중...")
    grouper = ArticleGrouper()
    groups, noise = grouper.group(articles)
    logger.info(f"그룹핑 완료: {len(groups)}개 그룹, {len(noise)}개 단일 기사.")

    # 3. 요약기 초기화
    summarizer = GptOssSummarizer()
    
    # 4. 각 그룹 처리 및 DB 저장
    try:
        with get_db() as db:
            # 4-1. 단일 기사(noise) 처리
            logger.info(f"{len(noise)}개의 단일 기사를 처리합니다...")
            for article in noise:
                logger.info(f"단일 기사 처리 중: {article['title'][:30]}...")
                summary = summarizer.refine_text(article['title'], article['body'])
                article['body'] = summary
                
                # crud 함수가 기대하는 데이터 형식에 맞춰 키를 추가/매핑합니다.
                if 'url' in article and 'source_url' not in article:
                    article['source_url'] = article['url']
                if 'source' in article and 'source_title' not in article:
                    article['source_title'] = article['title']
                if 'source' in article and 'press_company' not in article:
                    article['press_company'] = article['source']
                
                crud.create_single_article(db=db, article_data=article)

            # 4-2. 그룹 기사 처리
            logger.info(f"{len(groups)}개의 그룹 기사를 처리합니다...")
            for group in groups:
                if not group: continue
                
                representative_article = group[0]
                logger.info(f"그룹 대표 기사 처리 중: {representative_article['title'][:30]}... ({len(group)}개 기사)")

                # 그룹 내 모든 기사 본문을 하나로 합침
                text_to_summarize = "\n\n".join(
                    [art.get('body', '').strip() for art in group if art.get('body')]
                )
                
                summary = summarizer.refine_text(representative_article['title'], text_to_summarize)
                
                # 대표 기사 데이터 준비
                if 'url' in representative_article and 'source_url' not in representative_article:
                    representative_article['source_url'] = representative_article['url']
                
                representative_article_data = {
                    'title': representative_article['title'],
                    'body': summary,
                    'category': representative_article.get('category', '기타'),
                    'image_url': representative_article.get('image_url', ''),
                    'source_url': representative_article.get('source_url')
                }

                # 원본 기사 목록 준비
                source_articles_data = [
                    {
                        'title': art.get('title'),
                        'url': art.get('url'),
                        'press_company': art.get('source')
                    } for art in group
                ]
                
                crud.create_grouped_article(
                    db=db,
                    representative_article_data=representative_article_data,
                    source_articles_data=source_articles_data
                )

        logger.info(f"기사 처리 파이프라인 완료.")

    except Exception as e:
        logger.error(f"기사 처리 파이프라인 중 오류 발생: {e}", exc_info=True)


if __name__ == "__main__":
    print("이 스크립트는 외부(예: 파이프라인 조정자)에서 local_data_path 인자와 함께 호출되어야 합니다.")
