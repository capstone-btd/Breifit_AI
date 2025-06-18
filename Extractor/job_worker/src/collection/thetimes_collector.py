import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import json # JSON 파싱을 위해 추가
import random

from .base_collector import BaseCollector

class TheTimesCollector(BaseCollector):
    def __init__(self):
        super().__init__(site_name="the_times", base_url="https://www.thetimes.co.uk")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-GB,en;q=0.9' # 영국 사이트이므로 영국 영어 우선
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

        # 사용자가 제공한 다양한 목록 컨테이너 선택자들
        # data-testid 속성을 우선적으로 활용
        list_container_selectors = [
            {"tag": "div", "attrs": {"data-testid": "slice/ad/list-slice container"}},
            {"tag": "section", "attrs": {"class": "css-2wymkw"}}, # World 섹션 상단
            {"tag": "div", "attrs": {"class": "css-1luqq5m"}},
            {"tag": "div", "attrs": {"class": "article-container css-kwby65", "data-testid": "article-container"}},
            {"tag": "div", "attrs": {"class": "css-1fglklz"}}, # US 섹션 등
            {"tag": "div", "attrs": {"class": "css-1ovapnw"}}  # US 섹션 4열
        ]

        # 사용자가 제공한 다양한 개별 기사 항목 선택자들
        article_item_selectors = [
            {"tag": "div", "attrs": {"data-testid": "lead-article"}},
            {"tag": "div", "attrs": {"data-testid": "vertical-article"}},
            {"tag": "div", "attrs": {"data-testid": "horizontal-article"}},
            {"tag": "div", "attrs": {"class": re.compile(r"css-dwp5gw|css-167tk2u|css-13fsqun|composed-article-card-.*css-dwp5gw|css-crn8pc|css-1d2smxu|css-15403k6|css-j6p0ps")}},
             # css-dwp5gw가 매우 흔하게 사용됨. 다른 구체적인 클래스명도 포함.
        ]
        
        # 제목 및 링크를 포함하는 a 태그 클래스 패턴
        # article-headline 또는 css-xxxxxx 형태
        title_link_a_tag_class_pattern = re.compile(r"^(article-headline|css-)")


        processed_containers = set()

        for container_selector_info in list_container_selectors:
            tag_name = container_selector_info["tag"]
            attrs = container_selector_info["attrs"]
            # print(f"DEBUG: Trying container selector: <{tag_name} {attrs}>")
            
            # 한 페이지에 동일한 구조의 컨테이너가 여러개 나올 수 있음 (예: 광고 후 새 목록)
            # find_all로 모든 해당 컨테이너를 찾아서 순회
            containers = soup.find_all(tag_name, attrs=attrs)
            if not containers and tag_name == "div" and "data-testid" in attrs and attrs["data-testid"] == "slice/ad/list-slice container":
                 # css-13y27az 와 같은 래퍼 div를 못찾는 경우, 그 하위의 css-18xk854 (IN DEPTH 목록)를 직접 시도
                containers = soup.find_all("div", attrs={"data-testid":"article-container", "class":"css-18xk854"})


            for container in containers:
                # 컨테이너 식별자를 만들어 중복 처리 방지 (너무 복잡하면 간단히 hash(str(container)) 사용)
                container_id = str(container.attrs) 
                if container_id in processed_containers:
                    continue
                processed_containers.add(container_id)
                # print(f"DEBUG: Processing container: {container_id}")

                for item_selector_info in article_item_selectors:
                    item_tag_name = item_selector_info["tag"]
                    item_attrs = item_selector_info["attrs"]
                    
                    potential_articles_in_item_selector = container.find_all(item_tag_name, attrs=item_attrs)
                    # print(f"DEBUG:   Found {len(potential_articles_in_item_selector)} items with <{item_tag_name} {item_attrs}> in container {container_id}")

                    for item in potential_articles_in_item_selector:
                        # 링크 태그: data-testid 우선, 그 다음엔 다양한 class를 가진 a 태그
                        link_tag = item.find('a', href=True, class_=title_link_a_tag_class_pattern)
                        
                        if not link_tag: # 가끔 a 태그가 더 깊이 있을 수 있음 (예: div > div > a)
                            link_tag = item.find('a', href=True, recursive=True, class_=title_link_a_tag_class_pattern)

                        title_text = None
                        if link_tag:
                            # 제목: a 태그 내부의 span 또는 a 태그 자체 텍스트
                            span_in_a = link_tag.find('span')
                            if span_in_a and span_in_a.text.strip():
                                title_text = span_in_a.text.strip()
                            else:
                                title_text = link_tag.text.strip()
                        
                        if link_tag and title_text and len(title_text) > 5: # 제목이 너무 짧으면 제외
                            href = link_tag.get('href')
                            if href.startswith('/'): # 상대 경로 확인
                                full_url = urljoin(self.base_url, href)
                                
                                parsed_full_url = urlparse(full_url)
                                if parsed_full_url.netloc == urlparse(self.base_url).netloc and full_url not in links_found and \
                                   not full_url.endswith(category_url) and \
                                   re.search(r'/article/|/news/|/comment/|/sport/|/business/|/money/|/life/|/style/|/culture/', parsed_full_url.path, re.I) and \
                                   not re.search(r'(/section/|/topic/|/author/|/puzzles/|/search|/subscribe|/login|/video|/live)', parsed_full_url.path, re.I):
                                    article_links.append({'title': title_text, 'url': full_url})
                                    links_found.add(full_url)
        
        # 만약 위에서 못 찾았다면, 더 일반적인 탐색 시도 (이전 로직 일부 활용)
        if not article_links:
            print(f"[{self.site_name.upper()}] Specific selectors found 0 links. Trying generic fallback on {category_url}")
            generic_items = soup.find_all('a', href=True, class_=title_link_a_tag_class_pattern)
            for link_tag in generic_items:
                title_text = None
                span_in_a = link_tag.find('span')
                if span_in_a and span_in_a.text.strip():
                    title_text = span_in_a.text.strip()
                else:
                    title_text = link_tag.text.strip()

                if title_text and len(title_text) > 5:
                    href = link_tag.get('href')
                    if href.startswith('/'):
                        full_url = urljoin(self.base_url, href)
                        parsed_full_url = urlparse(full_url)
                        if parsed_full_url.netloc == urlparse(self.base_url).netloc and full_url not in links_found and \
                           not full_url.endswith(category_url) and \
                           re.search(r'/article/|/news/|/comment/|/sport/|/business/|/money/|/life/|/style/|/culture/', parsed_full_url.path, re.I) and \
                           not re.search(r'(/section/|/topic/|/author/|/puzzles/|/search|/subscribe|/login|/video|/live)', parsed_full_url.path, re.I):
                            article_links.append({'title': title_text, 'url': full_url})
                            links_found.add(full_url)


        if not article_links:
            print(f"[{self.site_name.upper()}] No article links found on {category_url}. Check selectors or page structure (or paywall).")
        else:
            # 중복 제거 (set을 사용했으므로 이미 어느정도 되었지만, dict list이므로 한번 더 확실히)
            unique_article_links = [dict(t) for t in {tuple(d.items()) for d in article_links}]
            print(f"[{self.site_name.upper()}] Found {len(unique_article_links)} unique article links on {category_url}.")
            return unique_article_links
        return []

    def _extract_text_from_paywalled_content(self, paywalled_content: list) -> list[str]:
        """Helper function to extract text from paywalledContent JSON structure."""
        parts = []
        if not isinstance(paywalled_content, list):
            return parts
            
        for item in paywalled_content:
            if isinstance(item, dict):
                if item.get("name") == "paragraph":
                    for child in item.get("children", []):
                        if isinstance(child, dict) and child.get("name") == "text" and "attributes" in child:
                            text_value = child["attributes"].get("value")
                            if text_value and isinstance(text_value, str):
                                parts.append(text_value.strip())
                # 더 많은 타입(예: 'heading', 'list')을 처리하려면 여기에 추가
                # elif item.get("name") == "image": # 이미지 캡션 등도 추가 가능
                #     caption = item.get("attributes", {}).get("caption")
                #     if caption: parts.append(f"[Image Caption: {caption.strip()}]")
        return parts

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        await asyncio.sleep(random.uniform(1, 3))
        print(f"[{self.site_name.upper()}/{category.upper()}] 기사 내용 가져오기 시작: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
        except Exception as e:
            print(f"[{self.site_name.upper()}/{category.upper()}] HTML 가져오는 중 알 수 없는 오류 ({article_url}): {e}")
            return None

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 새로운 간단한 추출 로직
        # 1. 제목 추출
        title_tag = soup.find('h1')
        article_title = title_tag.get_text(strip=True) if title_tag else original_title

        # 2. 이미지 추출 (og:image 우선, 없으면 본문 첫 이미지)
        main_image_url = None
        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.get('content'):
            main_image_url = og_image_tag['content']

        # 3. 본문 추출
        article_text_parts = []
        # The Times는 기사 본문을 담는 div나 article 태그가 유동적일 수 있음
        article_body = soup.select_one('div.sc-3c4f9a2-0, article[role="article"]')
        if article_body:
            paragraphs = article_body.find_all('p')
            for p in paragraphs:
                article_text_parts.append(p.get_text(strip=True))
        
        # 이미지를 찾지 못했고, 본문이 있다면 본문 첫 이미지라도 시도
        if not main_image_url and article_body:
            first_img_tag = article_body.find('img')
            if first_img_tag and first_img_tag.get('src'):
                main_image_url = first_img_tag.get('src')


        article_text = "\n".join(article_text_parts)

        if not article_text.strip():
            print(f"[{self.site_name.upper()}/{category.upper()}] No text found in article: {article_url} after all attempts.")
            return None
            
        return {
            "url": article_url,
            "title": article_title,
            "main_image_url": main_image_url,
            "article_text": article_text.strip(),
            "source": self.site_name,
            "category": category
        }

# 테스트용 코드 (선택자 구현 후 주석 해제)
# async def main_test():
#     # news_sites.yaml에 the_times와 카테고리 경로가 정확히 설정되어 있어야 함
#     collector = TheTimesCollector()
#     # test_category_url = "https://www.thetimes.co.uk/world" # 실제 카테고리 URL
#     # test_category_name = "World"
#     # collected_links = await collector.fetch_article_links(aiohttp.ClientSession(), test_category_url)
#     # if collected_links:
#     #     print(f"Found {len(collected_links)} links from {test_category_url}")
#     #     for link_info in collected_links[:2]: # 처음 2개 링크 테스트
#     #         print(f"  Title: {link_info['title']}, URL: {link_info['url']}")
#     #         content = await collector.fetch_article_content(aiohttp.ClientSession(), link_info['url'], link_info['title'])
#     #         if content:
#     #             print(f"    Collected content for: {content['title']}")
#     #             print(f"    Image: {content['main_image_url']}")
#     #             print(f"    Text: {content['article_text'][:200]}...")
#     #             if not content['article_text']: print("    WARN: Article text is empty!")
#     #         else:
#     #             print(f"    Failed to collect content for {link_info['url']}")
#     # else:
#     #     print(f"No links found from {test_category_url}")


#     # 단일 기사 테스트
#     # test_article_url = "https://www.thetimes.co.uk/article/kyiv-putin-drones-056mpjsfm" # 실제 기사 URL
#     # test_article_title = "Inside Ukraine's plan to track, jam and destroy Putin's drones" # 대략적인 제목
#     # async with aiohttp.ClientSession() as session:
#     #     content = await collector.fetch_article_content(session, test_article_url, test_article_title)
#     #     if content:
#     #         print(f"Collected content for: {content['title']}")
#     #         print(f"Image: {content['main_image_url']}")
#     #         print(f"Text: {content['article_text']}")
#     #     else:
#     #         print(f"Failed to collect content for {test_article_url}")


# if __name__ == '__main__':
#    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # Windows에서 필요할 수 있음
#    asyncio.run(main_test()) 