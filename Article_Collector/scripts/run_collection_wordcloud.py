# Collection
# 1. WordCloud DB에서 단어 배열을 받아온다.
# 2. 네이버 뉴스 API를 통해 단어별로 기사를 검색한다.
# 3. 검색된 기사들의 링크를 바탕으로 본문과 대표 이미지를 수집한다.
# 4. 수집된 데이터를 GCS에 JSON 형태로 저장한다.

import asyncio
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from slugify import slugify
import aiohttp
from google.cloud import storage
import io
from bs4 import BeautifulSoup
from newspaper import Article
from urllib.parse import urlparse, parse_qs
import ssl

# --- 기존 모듈 및 설정 ---
# 프로젝트 루트 경로 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, PROJECT_ROOT)  # 프로젝트 루트를 Python 경로에 추가
# sys.path.append(os.path.join(PROJECT_ROOT, '..', 'api_server'))

# 유틸리티 및 SQLAlchemy 관련 모듈
from src.utils.logger import setup_logger
from src.utils.text_processing import preprocess_text_simple
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager

# --- 네이버 뉴스 API 설정 ---
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "YJPNOQ0QKIigP1PTje9C")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "Il4qo4Qusq")
NAVER_API_URL = "https://openapi.naver.com/v1/search/news.json"

# --- 데이터베이스 설정 ---
DB_HOST = os.getenv("DB_HOST", "capstone2.cy1i8asionul.us-east-1.rds.amazonaws.com")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME", "briefit")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "chltjr123")
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TrendKeyword(Base):
    __tablename__ = 'wordcloud'
    id = Column(Integer, primary_key=True, index=True)
    score = Column(Integer, nullable=False)
    word = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- GCS 설정 ---
GCS_BUCKET_NAME = "betodi-gpu"
storage_client = None
bucket = None
# try:
#     storage_client = storage.Client()
#     bucket = storage_client.bucket(GCS_BUCKET_NAME)
#     print("[GCS] Google Cloud Storage 연결 성공")
# except Exception as e:
#     print(f"[GCS] Google Cloud Storage 연결 실패 (로컬 모드로 실행): {e}")

# --- 핵심 로직 ---

def fetch_wordcloud_keywords() -> List[str]:
    """데이터베이스에서 WordCloud 키워드를 가져옵니다."""
    try:
        with get_db() as db:
            keywords_query = db.query(TrendKeyword.word).all()
            word_list = list(set([kw.word.strip() for kw in keywords_query if kw.word and kw.word.strip()]))
            print(f"[DB] {len(word_list)}개의 키워드 로드: {word_list[:5]}...")
            return word_list
    except Exception as e:
        print(f"[DB] 키워드 로드 실패: {e}")
        return []

def get_naver_news_category(soup: BeautifulSoup, url: str) -> str:
    """네이버 뉴스 HTML과 URL을 분석하여 카테고리를 추출합니다."""
    # 1. HTML에서 카테고리 직접 추출 (가장 정확)
    category_element = soup.select_one('em.media_end_categorize_item strong')
    if category_element:
        return category_element.get_text(strip=True)

    # 2. URL의 sid 파라미터로 카테고리 추정
    sid_map = {
        '100': '정치', '101': '경제', '102': '사회', '103': '문화',
        '104': '세계', '105': 'IT', '108': '사회'
    }
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        sid = query_params.get('sid', [None])[0]
        if sid in sid_map:
            return sid_map[sid]
    except Exception:
        pass # URL 파싱 실패 시 무시

    return '기타' # 모든 방법 실패 시

async def search_naver_news(session: aiohttp.ClientSession, keyword: str, semaphore: asyncio.Semaphore) -> List[dict]:
    """네이버 뉴스 API로 키워드 검색을 수행합니다."""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": keyword, "display": 15, "sort": "sim"}
    
    async with semaphore: # 세마포를 통해 동시 요청 수 제어
        try:
            await asyncio.sleep(2) # 요청 간 짧은 지연 추가
            async with session.get(NAVER_API_URL, headers=headers, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get('items', [])
        except Exception as e:
            print(f"  - '{keyword}' 네이버 뉴스 검색 실패: {e}")
            return []

async def fetch_article_details(session: aiohttp.ClientSession, article_info: dict) -> Optional[dict]:
    """기사 링크를 방문하여 본문, 대표 이미지, 카테고리를 추출합니다."""
    naver_link = article_info.get('link')
    original_link = article_info.get('originallink')

    # 네이버 뉴스 링크(n.news.naver.com)가 있으면 우선 사용 (구조가 정형화되어 파싱 안정성이 높음)
    # 네이버 링크가 없거나 일반 naver.com 링크일 경우 originallink 사용
    if naver_link and "n.news.naver.com" in naver_link:
        link_to_crawl = naver_link
    elif original_link:
        link_to_crawl = original_link
    else:
        return None # 크롤링할 유효한 링크가 없음

    # 최종적으로 저장할 URL은 원본 기사 링크로 지정
    url_to_save = original_link or naver_link

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",  # 구글 검색을 통해 들어온 것처럼 위장
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        async with session.get(link_to_crawl, headers=headers, timeout=15) as response:
            response.raise_for_status()

            # 인코딩 문제 해결을 위해 raw byte를 읽고 디코딩 시도
            html_bytes = await response.read()
            try:
                html = html_bytes.decode('utf-8')
            except UnicodeDecodeError:
                html = html_bytes.decode('euc-kr', 'ignore') # utf-8 실패 시 euc-kr 시도
            
            article_text = ""
            image_url = ""
            category = "기타"
            source = ""

            if "n.news.naver.com" in link_to_crawl:
                soup = BeautifulSoup(html, 'html.parser')
                category = get_naver_news_category(soup, link_to_crawl) # 카테고리 추출
                
                # 언론사 이름 추출
                source_element = soup.select_one('a.media_end_head_top_logo_link img')
                if source_element and source_element.get('alt'):
                    source = source_element.get('alt')
                else: # 예외 케이스 처리
                    source_element = soup.select_one('.press_logo img')
                    if source_element and source_element.get('alt'):
                        source = source_element.get('alt')
                
                content_area = soup.select_one('#newsct_article')
                if content_area:
                    for el in content_area.select("em.img_desc, .end_photo_org"):
                        el.decompose()
                    article_text = content_area.get_text(separator='\n', strip=True)
                
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    image_url = og_image['content']
            else:
                # newspaper3k는 동기 라이브러리이므로 run_in_executor로 비동기 처리
                loop = asyncio.get_running_loop()
                article = await loop.run_in_executor(None, lambda: Article(link_to_crawl, language='ko'))
                await loop.run_in_executor(None, article.download, html)
                await loop.run_in_executor(None, article.parse)
                article_text = article.text
                image_url = article.top_image
                # 외부 기사는 카테고리 추정이 어려우므로 '기타'로 설정
                category = '기타'
                
                # newspaper3k에서 source 추출 시도 (안전하게)
                source = getattr(article, 'brand', None) # 'brand' 속성이 없을 수 있으므로 getattr 사용
                if not source and article.source_url:
                    parsed_url = urlparse(article.source_url)
                    # netloc에서 'www.' 등을 제거하여 깔끔한 도메인 이름만 사용
                    source = parsed_url.netloc.split('.')[-2] if '.' in parsed_url.netloc else parsed_url.netloc

            if article_text and len(article_text) > 30:
                title = article_info['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                return {
                    'title': title,
                    'url': url_to_save,
                    'article_text': article_text,
                    'image_url': image_url, # 'main_image_url' -> 'image_url'
                    'source': source,
                    'category': category # 추출한 카테고리 추가
                }
    except Exception as e:
        print(f"  - 상세 기사 수집 실패 ({link_to_crawl[:30]}...): {e}")
    return None

async def preprocess_article(article: dict) -> Optional[dict]:
    """수집된 기사를 전처리하고 유효성을 검사합니다."""
    if not all(k in article for k in ['title', 'url', 'article_text']):
        return None

    article['body'] = preprocess_text_simple(article['article_text'])
    del article['article_text']

    if len(article['body'].strip()) < 30:
        return None
    
    # 'image_url' 필드는 fetch 단계에서 이미 처리됨
    # if 'main_image_url' in article:
    #     article['image_url'] = article.pop('main_image_url')

    return article


async def upload_json_to_gcs_async(data: dict, gcs_path: str):
    """데이터를 JSON으로 GCS에 업로드하거나 로컬에 백업합니다."""
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    
    # if bucket:
    #     try:
    #         blob = bucket.blob(gcs_path)
    #         with io.BytesIO(json_bytes) as stream:
    #             blob.upload_from_file(stream, content_type='application/json')
    #         print(f"  - GCS 업로드 성공: {gcs_path}")
    #         return
    #     except Exception as e:
    #         print(f"  - GCS 업로드 실패, 로컬 저장: {e}")

    local_path = os.path.join(PROJECT_ROOT, 'Data', gcs_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, 'wb') as f:
        f.write(json_bytes)
    print(f"  - 로컬 저장 완료: {local_path}")


async def run_wordcloud_collection_pipeline() -> Optional[str]:
    """WordCloud 키워드 기반 뉴스 수집 및 저장 파이프라인"""
    logger = setup_logger()
    logger.info("======= WordCloud Collection Job Started (Naver API) =======")

    # 1. 키워드 로드
    keywords = fetch_wordcloud_keywords()
    if not keywords:
        logger.error("DB에서 키워드를 가져올 수 없어 수집을 중단합니다.")
        return None

    collection_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_prefix = f"collected_articles_wordcloud/{collection_time_str}"
    
    # 동시 요청을 10개로 제한하는 세마포 생성
    semaphore = asyncio.Semaphore(10)

    # SSL 컨텍스트 생성: 일부 사이트의 엄격한 SSL/TLS 정책에 대응
    # 보안 수준을 낮춰 호환성을 확보 (Handshake failure 방지)
    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 2. 키워드별 뉴스 검색 (병렬)
        search_tasks = [search_naver_news(session, kw, semaphore) for kw in keywords]
        search_results = await asyncio.gather(*search_tasks)
        
        all_news_items = [item for sublist in search_results for item in sublist]
        unique_urls = {item['link']: item for item in all_news_items} # 중복 URL 제거
        
        print(f"총 {len(unique_urls)}개의 고유한 기사 검색 완료. 상세 정보 수집 시작...")

        # 3. 기사 상세 정보 수집 (병렬)
        detail_tasks = [fetch_article_details(session, item) for item in unique_urls.values()]
        detailed_articles = await asyncio.gather(*detail_tasks)
        
        valid_articles = [art for art in detailed_articles if art]
        print(f"총 {len(valid_articles)}개의 유효한 기사 상세 정보 수집 완료. 전처리 및 저장 시작...")
        
        # 4. 전처리 및 저장 (병렬)
        saved_count = 0
        async def process_and_save(article_data: dict) -> bool:
            processed = await preprocess_article(article_data)
            if not processed:
                return False
            
            filename = f"{slugify(processed.get('title', 'untitled'))}.json"
            save_path = f"{output_prefix}/naver_api/{filename}"
            await upload_json_to_gcs_async(processed, save_path)
            return True

        save_tasks = [process_and_save(art) for art in valid_articles]
        results = await asyncio.gather(*save_tasks)
        saved_count = sum(1 for r in results if r)

    logger.info(f"WordCloud 수집 완료. 총 {saved_count}개의 기사를 저장했습니다.")
    
    if saved_count > 0:
        local_output_path = os.path.join(PROJECT_ROOT, 'Data', output_prefix, 'naver_api')
        logger.info(f"데이터 로컬 저장 위치: {local_output_path}")
        return local_output_path
    else:
        logger.info("새롭게 수집된 기사가 없습니다.")
        return None

async def main():
    """메인 실행 함수"""
    setup_logger()
    print("WordCloud 기반 뉴스 수집 파이프라인 시작 (Naver API 통합)...")
    saved_dir = await run_wordcloud_collection_pipeline()
    if saved_dir:
        print(f"\n스크립트 실행 완료. 수집된 기사들이 {saved_dir}에 저장되었습니다.")
    else:
        print("\n스크립트 실행 완료. 새롭게 수집된 기사가 없습니다.")

if __name__ == "__main__":
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())


