import asyncio, json
from pathlib import Path
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, FilterChain, URLPatternFilter
from bs4 import BeautifulSoup

# ────────────────────────────────
# 사용자 설정
# ────────────────────────────────
SEED_URL       = "https://news.naver.com/"
TARGET_COUNT   = 3000
OUT_DIR        = Path("./articles")
OUT_DIR.mkdir(exist_ok=True)

# 브라우저 (JS 실행은 기본)
BROWSER_CFG = BrowserConfig(headless=True)

# 기사 URL 패턴
def make_strategy(limit: int):
    return BFSDeepCrawlStrategy(
        filter_chain=FilterChain([
            URLPatternFilter(
                include_patterns=["https://n.news.naver.com/article/*/*"],
                exclude_patterns=["https://n.news.naver.com/article/comment/*/*"]
            )
        ]),
        max_depth=6,
        max_pages=limit * 3,
        include_external=False,
    )

ARTICLE_SELECTORS = [
    "#dic_area",
    "#articleBodyContents",
    "#articeBody",
    "#articeBodyContents",
    "#newsEndContents",
]

# ────────────────────────────────
# 크롤링
# ────────────────────────────────
async def crawl_naver():
    saved_urls: set[str] = set()
    run_cfg = CrawlerRunConfig(
        deep_crawl_strategy=make_strategy(TARGET_COUNT),
        cache_mode=CacheMode.BYPASS,
        page_timeout=60_000,
        wait_until="networkidle",     # 모든 네트워크 요청이 멈출 때까지
    )

    async with AsyncWebCrawler(config=BROWSER_CFG, concurrency=10) as crawler:
        print("[NAVER] 시작…")
        for res in await crawler.arun(SEED_URL, config=run_cfg):
            if not res.success or res.url == SEED_URL or res.url in saved_urls:
                continue

            soup = BeautifulSoup(res.html or "", "lxml")
            article_text = ""
            for sel in ARTICLE_SELECTORS:
                node = soup.select_one(sel)
                if node:
                    for t in node.select("script,style,noscript"):
                        t.decompose()
                    article_text = node.get_text(" ", strip=True)
                    break
            if not article_text:
                continue

            idx = len(saved_urls)
            (OUT_DIR / f"naver_{idx:05d}.json").write_text(
                json.dumps({"content": article_text}, ensure_ascii=False),
                encoding="utf-8",
            )
            saved_urls.add(res.url)
            print(f"✅ {idx+1:5d}/{TARGET_COUNT}  {res.url}")

            if len(saved_urls) >= TARGET_COUNT:
                break
    print(f"[NAVER] 완료 – {len(saved_urls)}개 저장")

if __name__ == "__main__":
    asyncio.run(crawl_naver())
