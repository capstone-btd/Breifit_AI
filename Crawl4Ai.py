""" This file is for Crwaling Article, News from other webs"""
import asyncio, re, json
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup

# n.news.naver.com/mnews 도메인의 링크를 찾는 정규표현식
ARTICLE_REGEX = re.compile(r"^https://n\.news\.naver\.com/mnews/article/\d+/\d+")

# ✅ 수집 대상 seed URL(우리가 정하는 뉴스 주제 키워드)
SEED_URLS = [
    "https://news.naver.com/main/ranking/popularDay.naver",  # 화제성
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=100",  # 정치
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=101",  # 경제
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=102",  # 사회
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=103",  # 생활/문화
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=104",  # 세계
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=105",  # IT/과학
]

def analyze_url_pattern(url):
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    return {
        'domain': parsed.netloc,
        'path_parts': path_parts,
        'query': parsed.query
    }

async def collect_varied_naver_links(limit_per_topic=10):
    article_links_by_topic = defaultdict(set)
    url_patterns = defaultdict(int)

    async with AsyncWebCrawler() as crawler:
        for seed_url in SEED_URLS:
            print(f"\n🌐 수집 중: {seed_url}")
            cfg = CrawlerRunConfig(exclude_external_links=True)
            seed_res = await crawler.arun(seed_url, config=cfg)

            if not seed_res.success:
                print(f"❌ 실패: {seed_url}")
                continue

            print(f"📊 발견된 내부 링크 수: {len(seed_res.links['internal'])}")
            
            # URL 패턴 분석
            for link in seed_res.links["internal"]:
                if "href" in link:
                    full_url = urljoin(seed_url, link["href"])
                    pattern = analyze_url_pattern(full_url)
                    pattern_key = f"{pattern['domain']}/{pattern['path_parts'][0] if pattern['path_parts'] else ''}"
                    url_patterns[pattern_key] += 1

                    if ARTICLE_REGEX.match(full_url):
                        article_links_by_topic[seed_url].add(full_url)
                        print(f"✅ 기사 링크 발견: {full_url}")

                        if len(article_links_by_topic[seed_url]) >= limit_per_topic:
                            print(f"🎯 {seed_url} 주제의 {limit_per_topic}개 기사 수집 완료")
                            break

    # URL 패턴 분석 결과 출력
    print("\n📊 URL 패턴 분석 결과:")
    for pattern, count in sorted(url_patterns.items(), key=lambda x: x[1], reverse=True):
        print(f"{pattern}: {count}개")

    # 모든 주제의 링크를 하나의 리스트로 합치기
    all_article_links = []
    for topic, links in article_links_by_topic.items():
        all_article_links.extend(list(links))
        print(f"\n📰 {topic} 주제 수집 결과: {len(links)}개")

    print(f"\n📰 최종 수집 기사 링크: {len(all_article_links)}개")
    if all_article_links:
        with open("naver_links_collected.json", "w", encoding="utf-8") as f:
            json.dump(sorted(all_article_links), f, ensure_ascii=False, indent=2)
        print("💾 링크 저장 완료")
    else:
        print("⚠️ 수집된 링크가 없습니다.")

    return all_article_links

async def crawl_article_content(crawler, url):
    try:
        res = await crawler.arun(url)
        if not res.success:
            return None

        soup = BeautifulSoup(res.html, 'html.parser')
        
        # 제목 추출
        title = soup.select_one('h2.media_end_head_headline')
        if not title:
            title = soup.select_one('h3.article_title')
        title = title.get_text().strip() if title else ""

        # 내용 추출
        content = soup.select_one('div#newsct_article')
        if not content:
            content = soup.select_one('div#articeBody')
        content = content.get_text().strip() if content else ""

        return {
            'url': url,
            'title': title,
            'content': content,
            'crawled_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error crawling {url}: {str(e)}")
        return None

async def main():
    # 링크 수집
    article_links = await collect_varied_naver_links()
    print(f"수집된 기사 링크: {len(article_links)}개")

    # 기사 내용 크롤링
    articles = []
    async with AsyncWebCrawler() as crawler:
        for url in article_links:
            article = await crawl_article_content(crawler, url)
            if article:
                articles.append(article)
                print(f"크롤링 완료: {article['title']}")
                print(f"크롤링 완료: {article['content']}")

    # 결과 저장
    if articles:
        output_file = f"naver_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"\n크롤링 완료: {len(articles)}개 기사 저장됨")
        print(f"저장 위치: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
