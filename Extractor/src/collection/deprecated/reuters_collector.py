import asyncio
import aiohttp
# from bs4 import BeautifulSoup # BeautifulSoup은 링크 수집에 더 이상 사용 안 함
from urllib.parse import urljoin # 본문 수집 시 이미지 URL 처리에 필요할 수 있음
import re
import feedparser # feedparser 임포트

from .base_collector import BaseCollector

class ReutersCollector(BaseCollector):
    def __init__(self):
        super().__init__(site_name="reuters", base_url="https://www.reuters.com")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, rss_feed_url: str) -> list[dict]:
        """주어진 RSS 피드 URL에서 기사 제목과 URL 목록을 추출합니다."""
        await asyncio.sleep(1) # Polite delay
        print(f"[{self.site_name.upper()}] Fetching article links from RSS feed: {rss_feed_url}")
        article_links = []
        
        try:
            # aiohttp를 사용하여 비동기적으로 RSS 피드 내용을 가져옵니다.
            async with session.get(rss_feed_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                feed_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] Timeout error fetching RSS feed: {rss_feed_url}")
            return []
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] ClientError fetching RSS feed: {e}, URL: {rss_feed_url}")
            return []
        except Exception as e:
            print(f"[{self.site_name.upper()}] Unknown error fetching RSS feed ({rss_feed_url}): {e}")
            return []

        # feedparser를 사용하여 RSS 피드 파싱
        try:
            parsed_feed = feedparser.parse(feed_content)
        except Exception as e:
            print(f"[{self.site_name.upper()}] Error parsing RSS feed ({rss_feed_url}): {e}")
            return []

        if parsed_feed.bozo:
            # bozo가 1이면 잘 구성되지 않은 피드일 수 있지만, 내용이 있을 수 있음
            bozo_exception = parsed_feed.bozo_exception
            print(f"[{self.site_name.upper()}] Warning: RSS feed ({rss_feed_url}) may be ill-formed. Bozo Exception: {bozo_exception}")

        links_found = set() # 중복 URL 방지용

        for entry in parsed_feed.entries:
            title = entry.get("title")
            link = entry.get("link")

            if title and link and link not in links_found:
                # 로이터 기사 링크인지 간단히 확인 (옵션)
                # if not self.base_url in link and not link.startswith("http://feeds.reuters.com/"):
                #     print(f"[{self.site_name.upper()}] Skipping non-Reuters link from RSS: {link}")
                #     continue
                
                article_links.append({"title": title, "url": link})
                links_found.add(link)
            elif not title:
                print(f"[{self.site_name.upper()}] RSS entry without title found in {rss_feed_url}. Link: {link}")
            elif not link:
                print(f"[{self.site_name.upper()}] RSS entry without link found in {rss_feed_url}. Title: {title}")

        if not article_links:
            print(f"[{self.site_name.upper()}] No article links found in RSS feed {rss_feed_url}. Check feed or parsing logic.")
        else:
            print(f"[{self.site_name.upper()}] Found {len(article_links)} unique article links from RSS feed {rss_feed_url}.")
        
        return article_links

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        await asyncio.sleep(1)
        print(f"[{self.site_name.upper()}] Fetching content for: {original_title} ({article_url})")
        try:
            # 본문 수집은 기존 방식 시도 (BeautifulSoup 사용)
            # 로이터에서 이 부분을 차단할 가능성이 여전히 있음
            async with session.get(article_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] Timeout error fetching article: {article_url}")
            return None
        except aiohttp.ClientError as e:
            # 403 Forbidden 등의 오류가 여기서 발생할 수 있음
            print(f"[{self.site_name.upper()}] ClientError fetching article: {e}, URL: {article_url}")
            return None
        except Exception as e:
            print(f"[{self.site_name.upper()}] Unknown error fetching article HTML ({article_url}): {e}")
            return None

        # BeautifulSoup 임포트가 fetch_article_content 내에서만 필요하면 여기로 옮기거나,
        # 클래스 레벨에 두되, fetch_article_links에서는 사용하지 않음을 명시
        from bs4 import BeautifulSoup # fetch_article_content에서만 사용
        soup = BeautifulSoup(html_content, 'html.parser')
        article_title = original_title
        main_image_url = None
        article_text_parts = []

        # 1. 메타 태그에서 제목 추출
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            article_title = og_title['content']
        else:
            title_tag = soup.find('h1', attrs={'data-testid': 'Heading'})
            if not title_tag: 
                title_tag = soup.find('h1')
            if title_tag:
                article_title = title_tag.text.strip()
        
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            main_image_url = og_image['content']
        else:
            image_container = soup.find('div', class_=re.compile(r'article-body__figure|Slideshow__container')) 
            if image_container:
                img_tag = image_container.find('img', src=True)
                if img_tag:
                    main_image_url = urljoin(article_url, img_tag.get('src'))
            if not main_image_url:
                figure_tag = soup.find('figure')
                if figure_tag:
                    img_tag = figure_tag.find('img', src=True)
                    if img_tag:
                        main_image_url = urljoin(article_url, img_tag.get('src'))

        # 본문 추출: #maincontent ID를 가진 요소를 우선 탐색
        article_body_container = soup.find(id='maincontent') # div, main, article 등 태그 무관하게 id로 검색

        if not article_body_container:
            # #maincontent가 없을 경우, 기존의 data-testid 또는 class 기반 탐색 시도
            print(f"[{self.site_name.upper()}] #maincontent not found for {article_url}. Trying other selectors.")
            article_body_container = soup.find('div', attrs={'data-testid': 'ArticleBody'})
            if not article_body_container:
                article_body_container = soup.find('div', class_=re.compile(r"(article-body|article-content|body-content|wysiwyg-body)", re.I))
            if not article_body_container: 
                article_body_container = soup.find('article')
        
        if article_body_container:
            paragraphs = []
            content_blocks = article_body_container.find_all('div', attrs={'data-testid': re.compile(r'paragraph-')})
            if content_blocks:
                for block in content_blocks:
                    paragraphs.extend(block.find_all('p'))
            else:
                paragraphs = article_body_container.find_all('p', class_=re.compile(r'(text__text__|article-body__content__|body__paragraph)', re.I))
                if not paragraphs: 
                    paragraphs = article_body_container.find_all('p')

            for p in paragraphs:
                text = p.text.strip()
                if text and not re.search(r'(Reporting by|Editing by|Our Standards:|The Thomson Reuters Trust Principles|All quotes delayed|Sign up for our newsletter)', text, re.I) \
                   and not p.find_parent('aside') and not p.find_parent(class_=re.compile(r'(ad|promo|related|footer|sidebar)')):
                    article_text_parts.append(text)
        else:
            # RSS에서 링크를 가져왔으므로, 본문 수집 실패는 흔할 수 있음.
            # 이 경우 요약 정보만이라도 저장하고 싶다면, RSS entry에서 summary를 가져와서 사용할 수 있음.
            # 여기서는 일단 기존처럼 None 반환.
            print(f"[{self.site_name.upper()}] Article body container not found for {article_url} (from RSS). Check selectors or site blocking.")
            # RSS entry에서 summary를 가져와서 article_text로 사용하는 예시:
            # summary = original_title # RSS에서 제목을 가져왔으므로, 만약 content가 없다면 제목을 본문으로...
            # for entry in parsed_feed.entries: # 이 방식은 fetch_article_links의 parsed_feed에 접근해야해서 구조 변경 필요
            #     if entry.link == article_url and entry.get("summary"):
            #         summary = entry.summary
            #         break
            # if summary:
            #     article_text_parts.append(BeautifulSoup(summary, 'html.parser').text.strip()) # HTML 태그 제거
            # else:
            #     return None # 요약도 없으면 포기
            return None # 일단 기존 로직 유지

        if not article_text_parts:
            print(f"[{self.site_name.upper()}] No text found in article: {article_url} (from RSS)")
            return None

        full_article_text = '\n\n'.join(article_text_parts)

        return {
            'url': article_url,
            'title': str(article_title).strip() if article_title else original_title.strip(),
            'main_image_url': str(main_image_url).strip() if main_image_url else None,
            'article_text': full_article_text.strip()
        }

# 테스트용 코드 (실행시 주석 해제)
# async def main_test():
#     # 테스트를 위해서는 news_sites.yaml의 reuters 카테고리에 실제 RSS 피드 URL을 넣어야 합니다.
#     # 예: world: "http://feeds.reuters.com/reuters/worldNews"
#     collector = ReutersCollector()
#     # 테스트할 카테고리 (news_sites.yaml의 키 값, 실제로는 RSS URL이어야 함)
#     test_category_rss_url = "http://feeds.reuters.com/reuters/worldNews" # 실제 테스트 시 유효한 RSS URL로 변경
#     test_category_display_name = "World News (RSS Test)"
#     
#     # collect_by_category는 category_path_segment를 받으므로, RSS URL을 여기에 전달
#     # 단, BaseCollector의 collect_by_category는 category_url = f"{self.base_url}/{category_path_segment}" 와 같이 사용하므로,
#     # ReutersCollector에서는 이 category_path_segment가 바로 RSS URL이 되도록 해야 함.
#     # 이 테스트를 위해서는 BaseCollector의 collect_by_category 동작을 이해하고, 
#     # 혹은 ReutersCollector에서 collect_by_category를 오버라이드하여 RSS URL을 직접 사용하도록 해야 할 수 있음.
#     # 여기서는 fetch_article_links가 RSS URL을 직접 받는다고 가정하고, 
#     # collect_by_category를 통해 실행하려면 YAML 설정이 올바르게 되어있어야 함.

#     # 직접 fetch_article_links 테스트 예시 (더 간단함)
#     async with aiohttp.ClientSession() as session:
#         links = await collector.fetch_article_links(session, test_category_rss_url)
#         if links:
#             print(f"\nFound {len(links)} links from {test_category_rss_url}")
#             # 첫 번째 링크에 대해 본문 수집 테스트
#             if len(links) > 0:
#                 first_link = links[0]
#                 print(f"Fetching content for: {first_link['title']} ({first_link['url']})")
#                 content = await collector.fetch_article_content(session, first_link['url'], first_link['title'])
#                 if content:
#                     print("Content fetched successfully:")
#                     print(f"  Title: {content['title']}")
#                     print(f"  Image: {content['main_image_url']}")
#                     print(f"  Text: {content['article_text'][:200]}...")
#                 else:
#                     print("Failed to fetch content.")
#         else:
#             print(f"No links found from {test_category_rss_url}")

# if __name__ == '__main__':
#    asyncio.run(main_test()) 