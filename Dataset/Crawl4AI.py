import asyncio
import json
import random
import sys
from pathlib import Path
import os

from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from crawl4ai.deep_crawling import (
    BFSDeepCrawlStrategy,
    FilterChain,
    URLPatternFilter,
)

# ────────────────────────────────
# 사용자 설정
# ────────────────────────────────
SEED_URLS = [
    "https://news.naver.com/",
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=100",  # 정치
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=101",  # 경제
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=102",  # 사회
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=103",  # 생활/문화
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=104",  # 세계
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=105",  # IT/과학
]

BATCH_SIZE = 10
TOTAL_TARGET = 5000
OUT_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "articles"
OUT_DIR.mkdir(exist_ok=True)

print(f"저장 경로: {OUT_DIR}")

# 브라우저 설정
BROWSER_CFG = BrowserConfig(
    headless=True,
    ignore_https_errors=True  # 인증서 오류 무시
)

# ────────────────────────────────
# 크롤링 전략
# ────────────────────────────────
# 🆕 기사·댓글 URL 허용/차단 패턴
ARTICLE_PATTERNS = [
    # ✅ 허용
    "https://n.news.naver.com/mnews/article/*/*",
    "https://n.news.naver.com/mnews/ranking/article/*/*",
    "https://n.news.naver.com/mnews/hotissue/article/*/*",
    "https://n.news.naver.com/article/*/*",
    "https://n.news.naver.com/ranking/article/*/*",
    "https://n.news.naver.com/hotissue/article/*/*",
    "https://news.naver.com/main/read.naver*",
    "https://news.naver.com/article/*/*",
    "https://news.naver.com/ranking/read.naver*",
    "https://news.naver.com/hotissue/article/*/*",

    # 🚫 차단 (댓글 뷰)
    "!https://n.news.naver.com/*/article/comment/*/*",
    "!https://n.news.naver.com/*/comment/*",
    "!https://news.naver.com/*/article/comment/*/*",
    "!https://news.naver.com/*/comment/*"
]


def make_strategy(limit: int) -> BFSDeepCrawlStrategy:
    """기사만 수집하도록 필터링한 BFS 딥 크롤 전략"""
    return BFSDeepCrawlStrategy(
        filter_chain=FilterChain([
            URLPatternFilter(patterns=ARTICLE_PATTERNS)
        ]),
        max_depth=5,
        max_pages=limit * 3,  # depth·branch factor 감안
        include_external=False,
    )

# 본문을 찾을 CSS 선택자
ARTICLE_SELECTORS = [
    "#dic_area", "#articleBodyContents", "#articeBody", "#articeBodyContents",
    "#newsEndContents", ".article_body", ".article_view",
]

# ────────────────────────────────
# 크롤링 코어
# ────────────────────────────────
async def crawl_naver(start_idx: int, target_count: int, shared_urls: set[str]) -> None:
    """네이버 기사 target_count 개 저장 (start_idx 부터)"""
    saved_urls: set[str] = set()
    saved_count = 0  # 실제 저장된 파일 수 추적

    run_cfg = CrawlerRunConfig(
        deep_crawl_strategy=make_strategy(target_count),
        cache_mode=CacheMode.BYPASS,
        page_timeout=120_000,
        wait_until="load"         # domcontentloaded 보다 안전
    )

    async with AsyncWebCrawler(config=BROWSER_CFG, concurrency=10) as crawler:
        batch_no = start_idx // BATCH_SIZE + 1
        print(f"\n[NAVER] 배치 {batch_no} 시작... (목표: {target_count}개)")
        seed_url = random.choice(SEED_URLS)
        print(f"시드 URL: {seed_url}")

        results = await crawler.arun(seed_url, config=run_cfg)
        for res in results:
            # 요청 실패 또는 시드 URL 자체는 건너뜀
            if not res.success or res.url == seed_url:
                continue

            # 전체 실행 중 이미 저장된 기사라면 건너뜀
            if res.url in shared_urls:
                print(f"  ⏩ 중복 URL 건너뜀: {res.url}")
                continue

            # 페이지 본문 추출
            soup = BeautifulSoup(res.html or "", "lxml")
            article_text = ""
            for sel in ARTICLE_SELECTORS:
                node = soup.select_one(sel)
                if node:
                    for t in node.select("script,style,noscript,iframe"):
                        t.decompose()
                    article_text = node.get_text(" ", strip=True)
                    break

            # 최소 길이 미달 시 건너뜀
            if len(article_text) < 100:
                print(f"  ⏩ 너무 짧은 기사 건너뜀: {len(article_text)}자")
                continue

            # 저장
            idx = start_idx + saved_count
            output_file = OUT_DIR / f"naver_{idx:05d}.json"
            try:
                output_file.write_text(
                    json.dumps({"content": article_text}, ensure_ascii=False),
                    encoding="utf-8",
                )
                saved_count += 1
                print(f"✅ {idx + 1:5d}/{TOTAL_TARGET}  {res.url}")
                print(f"   저장됨: {output_file} ({len(article_text)}자)")
            except Exception as e:
                print(f"❌ 저장 실패: {output_file} - {str(e)}")
                continue

            saved_urls.add(res.url)
            shared_urls.add(res.url)

            if saved_count >= target_count:
                print(f"\n목표 달성: {saved_count}개 저장 완료")
                break

    print(f"\n[NAVER] 배치 {batch_no} 완료 – {saved_count}개 저장")
    print(f"현재까지 총 {len(shared_urls)}개의 고유 URL 수집")

# ────────────────────────────────
# 배치 실행 헬퍼
# ────────────────────────────────
def run_batch(batch_num: int, shared_urls: set[str]) -> None:
    """단일 배치 실행 (동기 래퍼)"""
    start_idx = batch_num * BATCH_SIZE
    target_count = min(BATCH_SIZE, TOTAL_TARGET - start_idx)
    asyncio.run(crawl_naver(start_idx, target_count, shared_urls))

# ────────────────────────────────
# 메인 진입점
# ────────────────────────────────
if __name__ == "__main__":
    num_batches = (TOTAL_TARGET + BATCH_SIZE - 1) // BATCH_SIZE
    shared_urls: set[str] = set()

    if len(sys.argv) > 1:
        # 인수로 특정 배치만 실행
        batch_num = int(sys.argv[1])
        if 0 <= batch_num < num_batches:
            run_batch(batch_num, shared_urls)
        else:
            print(f"유효하지 않은 배치 번호입니다. 0-{num_batches - 1} 사이 입력")
    else:
        # 순차로 전체 배치 실행
        for i in range(num_batches):
            run_batch(i, shared_urls)
