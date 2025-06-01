import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

from .base_collector import BaseCollector

class GuardianCollector(BaseCollector):
    def __init__(self):
        super().__init__(site_name="the_guardian", base_url="https://www.theguardian.com")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-GB,en;q=0.9' # The Guardian은 영국 기반이므로 영국 영어 우선
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        await asyncio.sleep(1)
        print(f"[{self.site_name.upper()}] Fetching article links from: {category_url}")
        article_links = []
        try:
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] Timeout error fetching page: {category_url}")
            return []
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] ClientError fetching page: {e}, URL: {category_url}")
            return []
        except Exception as e:
            print(f"[{self.site_name.upper()}] Unknown error fetching HTML ({category_url}): {e}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        links_found = set()

        # The Guardian 기사 링크는 주로 <a class="fc-item__link"> 또는 <a class="u-faux-block-link__overlay"> 와 같은 형태입니다.
        # 제목은 보통 fc-item__title 또는 이와 유사한 클래스의 h3, h2 등에 있습니다.
        # data-link-name="article" 속성을 가진 a 태그를 찾는 것도 좋은 방법입니다.
        
        # 1. data-link-name="article"을 가진 <a> 태그 탐색
        link_tags = soup.find_all('a', attrs={'data-link-name': 'article'}, href=True)
        
        if not link_tags:
            # 2. fc-item__link 클래스를 가진 <a> 태그 탐색
            link_tags.extend(soup.find_all('a', class_='fc-item__link', href=True))
        
        if not link_tags:
            # 3. 좀 더 일반적인 카드형 구조에서 링크 탐색 (예: dcr- C L A S S E S)
            # The Guardian은 dcr-로 시작하는 동적 클래스를 많이 사용합니다.
            # 예를 들어, <div class="dcr-1x2x3x"> <a href="..."><h3>...</h3></a> </div>
            # fc-container, fc-slice, dcr- (어떤 패턴) 내부의 a 태그
            card_containers = soup.find_all('div', class_=re.compile(r'^(fc-(container|slice|item)|dcr-\w+|zone-)\w*'))
            for container in card_containers:
                # 카드 컨테이너 내에서 첫 번째 유효한 링크와 제목을 찾으려고 시도
                a_tag = container.find('a', href=True)
                if a_tag and a_tag not in link_tags:
                    link_tags.append(a_tag)
        
        for link_tag in link_tags:
            href = link_tag.get('href')
            title_text = None

            # 제목 추출 시도
            # 1. 링크 태그 내의 fc-item__title, u-faux-block-link__cta, dcr- 스타일 제목
            title_element = link_tag.find(['h1','h2','h3','h4', 'span'], class_=re.compile(r'(fc-item__title|js-headline-text|u-faux-block-link__cta|dcr-\w+__title)', re.I))
            if title_element:
                title_text = title_element.text.strip()
            else:
                # 2. 링크 태그의 aria-label 또는 내부 텍스트
                aria_label = link_tag.get('aria-label')
                if aria_label and len(aria_label) > 10:
                    title_text = aria_label.strip()
                elif link_tag.text.strip() and len(link_tag.text.strip()) > 10:
                    title_text = link_tag.text.strip()
            
            if href and title_text and href not in links_found:
                # The Guardian URL은 대부분 base_url로 시작합니다.
                if not href.startswith('http'):
                    full_url = urljoin(self.base_url, href)
                else:
                    full_url = href
                
                # 유효한 기사 URL인지, base_url로 시작하는지, 그리고 특정 필터링 (liveblogs, galleries 등)
                if full_url.startswith(self.base_url) and \
                   not re.search(r'/(live|gallery|video|audio|crosswords|cartoon|picture|inpictures|interactive|liveblog)s?/\d+', full_url, re.I) and \
                   not re.search(r'/ng-interactive/|/profile/|/email/|/contributors/', full_url, re.I) and \
                   (full_url.count('/') >= 4): # 일반적으로 /section/year/month/day/title 형태
                    
                    normalized_category_url = category_url.rstrip('/')
                    normalized_full_url = full_url.rstrip('/')
                    if normalized_full_url == normalized_category_url or normalized_full_url == self.base_url.rstrip('/'):
                        continue

                    article_links.append({'title': title_text, 'url': full_url})
                    links_found.add(href)
                    links_found.add(full_url)

        final_links = []
        seen_urls = set()
        for link_info in article_links:
            if link_info['url'] not in seen_urls:
                final_links.append(link_info)
                seen_urls.add(link_info['url'])
        article_links = final_links

        if not article_links:
            print(f"[{self.site_name.upper()}] No article links found on {category_url}. Check selectors or page structure.")
        else:
            print(f"[{self.site_name.upper()}] Found {len(article_links)} unique article links on {category_url}.")
        return article_links

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        await asyncio.sleep(1)
        print(f"[{self.site_name.upper()}] Fetching content for: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] Timeout error fetching article: {article_url}")
            return None
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] ClientError fetching article: {e}, URL: {article_url}")
            return None
        except Exception as e:
            print(f"[{self.site_name.upper()}] Unknown error fetching article HTML ({article_url}): {e}")
            return None

        soup = BeautifulSoup(html_content, 'html.parser')
        article_title = original_title
        main_image_url = None
        article_text_parts = []

        # 제목 추출 (og:title 메타 태그 우선)
        og_title_tag = soup.find('meta', property='og:title')
        if og_title_tag and og_title_tag.get('content'):
            article_title = og_title_tag['content']
        else:
            # dcr- 접두사를 가진 h1 태그 또는 일반 h1 태그
            title_h1 = soup.find('h1', class_=re.compile(r'^dcr-')) 
            if not title_h1: # dcr- h1이 없으면 일반 h1 탐색
                title_h1 = soup.find('h1')
            if title_h1:
                article_title = title_h1.text.strip()

        # 이미지 URL 추출 (og:image 메타 태그 우선)
        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.get('content'):
            main_image_url = og_image_tag['content']
        else:
            # dcr- 접두사를 가진 figure 또는 picture 내부의 img 태그
            # 예시: <figure class="dcr-1sughvz"> <picture class="dcr-u0h1qy"> <img ... > 
            # 또는 div class="dcr-bac4hp" role="figure" 안에 img
            image_container = soup.find(lambda tag: tag.name == 'figure' and tag.has_attr('class') and any(cls.startswith('dcr-') for cls in tag['class']))
            if not image_container: # figure가 없으면 picture 태그 시도
                image_container = soup.find(lambda tag: tag.name == 'picture' and tag.has_attr('class') and any(cls.startswith('dcr-') for cls in tag['class']))
            if not image_container: # 그래도 없으면 role=figure인 div 탐색
                image_container = soup.find('div', attrs={'role': 'figure'}, class_=re.compile(r'^dcr-'))
            
            if image_container:
                img_tag = image_container.find('img', src=True)
                if img_tag:
                    main_image_url = urljoin(article_url, img_tag.get('src'))

        # 본문 추출
        # 가디언은 data-gu-name="body" 또는 class^="dcr-" 과 같은 article 블록 사용
        # 또는 id="maincontent" 내부의 article/div.content__article-body 로 시도
        article_body_container = soup.find('div', attrs={'data-gu-name': 'body'})
        if not article_body_container:
            article_body_container = soup.find('article', class_=re.compile(r'^dcr-')) # dcr- 접두사 클래스를 가진 article
        if not article_body_container: # 추가 탐색
            main_content = soup.find('div', id='maincontent')
            if main_content:
                article_body_container = main_content.find(['article', 'div'], class_=re.compile(r'(content__article-body|article-body)', re.I))
        if not article_body_container:
            article_body_container = soup.find('main', id='maincontent') # main#maincontent 내부도 확인

        if article_body_container:
            # 가디언은 p 태그에 class="dcr-[random]-paragraph" 또는 그냥 p 태그 사용
            paragraphs = article_body_container.find_all('p', class_=re.compile(r'^dcr-.*?paragraph$'))
            if not paragraphs: # dcr- paragraph가 없으면 일반 p 탐색
                paragraphs = article_body_container.find_all('p')

            for p in paragraphs:
                # 가디언은 캡션이나 광고성 문구를 <aside> 태그 또는 특정 클래스로 감싸는 경우가 있음
                # 또는 <p><strong>관련 기사:</strong>...</p> 와 같은 패턴도 제외
                text = p.text.strip()
                if text and len(text) > 25 and \
                   not p.find_parent('aside') and \
                   not p.find_parent(class_=re.compile(r'(submeta|meta|caption|related|advert|supporting|cta|syndication|newsletter)', re.I)) and \
                   not (p.find('strong') and re.search(r'(related|read more|subscribe|sign up)', p.find('strong').text, re.I)):
                    article_text_parts.append(text)
        else:
            print(f"[{self.site_name.upper()}] Article body container not found for {article_url}. Check selectors.")
            return None

        if not article_text_parts:
            print(f"[{self.site_name.upper()}] No text found in article: {article_url}")
            return None

        full_article_text = '\n\n'.join(article_text_parts)

        # 모든 반환 값에 대해 str() 처리 및 None일 경우 기본값 처리
        return {
            'url': article_url,
            'title': str(article_title).strip() if article_title else original_title.strip(),
            'main_image_url': str(main_image_url).strip() if main_image_url else None,
            'article_text': full_article_text.strip(),
            'source': "the guardian"
        }

# 테스트용 코드
# async def main_test():
#     collector = GuardianCollector()
#     test_category_path = "world" # news_sites.yaml의 a key
#     collected_articles = await collector.collect_by_category("World News", test_category_path) # Display name, path
    
#     if collected_articles:
#         print(f"\nSuccessfully collected {len(collected_articles)} articles from The Guardian - {test_category_path}.")
#         # for i, article in enumerate(collected_articles):
#         #     print(f"\n--- Article {i+1} ---")
#         #     print(f"Title: {article['title']}")
#         #     print(f"URL: {article['url']}")
#         #     print(f"Image: {article['main_image_url']}")
#         #     # print(f"Text: {article['article_text'][:200]}...")
#         #     if not article['article_text']:
#         #         print("WARN: Article text is empty!")
#     else:
#         print(f"\nFailed to collect articles from The Guardian - {test_category_path}.")

# if __name__ == '__main__':
#    asyncio.run(main_test()) 