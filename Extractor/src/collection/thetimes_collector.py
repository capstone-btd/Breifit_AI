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
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}/{category.upper()}] 기사 페이지 로딩 시간 초과: {article_url}")
            return None
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}/{category.upper()}] 기사 페이지 로딩 중 ClientError: {e}, URL: {article_url}")
            return None
        except Exception as e:
            print(f"[{self.site_name.upper()}/{category.upper()}] HTML 가져오는 중 알 수 없는 오류 ({article_url}): {e}")
            return None

        soup = BeautifulSoup(html_content, 'html.parser')
        article_title = original_title
        main_image_url = None
        article_text_parts = []
        apollo_state = None

        # 1. window.__APOLLO_STATE__ 에서 JSON 데이터 추출 시도
        try:
            script_tag = soup.find('script', string=re.compile(r'window\.__APOLLO_STATE__\s*='))
            if script_tag:
                script_content = script_tag.string
                json_str = script_content.split('window.__APOLLO_STATE__ = ', 1)[1].strip()
                # 스크립트 태그가 끝나는 지점까지 잘라내기 (가끔 뒤에 다른 JS 코드가 붙는 경우 방지)
                if json_str.endswith(';'): # ;로 끝나면 제거
                    json_str = json_str[:-1]
                
                # JSON 객체가 여러 개 최상위에 있는 경우 (드물지만, 가끔 Apollo가 상태를 분리 저장)
                # 대부분은 단일 객체. 예시: { ... }
                # 만약 { ... } { ... } 형태라면 첫번째 것만 사용하거나, merge 로직 필요.
                # 여기서는 첫번째 유효한 JSON 객체를 파싱 시도.
                # 복잡한 케이스: window.__APOLLO_STATE__ = {...}; window.anotherVar = ...;
                # 이 경우, 첫번째 세미콜론 전까지가 JSON이어야 함.
                # 또는, JSON이 여러 줄로 나뉘어져 있을 수 있음.
                # 가장 단순한 방법은 첫번째 { 부터 마지막 } 까지를 추출하는 것.
                
                # 첫 '{' 와 마지막 '}' 사이를 추출 (더 견고한 방법 필요할 수 있음)
                first_brace = json_str.find('{')
                last_brace = json_str.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_to_parse = json_str[first_brace : last_brace+1]
                    try:
                        apollo_state = json.loads(json_to_parse)
                        # print(f"[{self.site_name.upper()}] Successfully parsed window.__APOLLO_STATE__ for {article_url}")
                    except json.JSONDecodeError as je:
                        print(f"[{self.site_name.upper()}] Failed to decode JSON from APOLLO_STATE for {article_url}: {je}")
                        # print(f"Problematic JSON string part: {json_to_parse[:500]}...") # 디버깅용
                        apollo_state = None # 파싱 실패 시 None으로 설정
                else:
                    print(f"[{self.site_name.upper()}] Could not find valid JSON structure in APOLLO_STATE for {article_url}")

        except Exception as ex:
            print(f"[{self.site_name.upper()}] Error processing APOLLO_STATE for {article_url}: {ex}")
            apollo_state = None

        if apollo_state:
            # APOLLO_STATE 내에서 Article 객체 찾기 (키 이름이 Article:GUID 형태)
            article_data = None
            lead_asset_data = None
            image_key = None

            for key, value in apollo_state.items():
                if key.startswith("Article:") and isinstance(value, dict):
                    article_data = value
                    # 제목 추출 (우선순위: headline, shortHeadline, name)
                    if article_data.get("headline"):
                        article_title = str(article_data["headline"]).strip()
                    elif article_data.get("shortHeadline"):
                        article_title = str(article_data["shortHeadline"]).strip()
                    elif article_data.get("name"): # 가끔 name 필드에 제목이 있을 수 있음
                         article_title = str(article_data["name"]).strip()
                    
                    # 대표 이미지 키 (leadAsset)
                    if isinstance(article_data.get("leadAsset"), dict) and article_data["leadAsset"].get("id"):
                        image_key = article_data["leadAsset"]["id"]
                    
                    # 본문 내용 (paywalledContent)
                    paywalled_content_json = article_data.get("paywalledContent")
                    if paywalled_content_json and isinstance(paywalled_content_json, list):
                        article_text_parts.extend(self._extract_text_from_paywalled_content(paywalled_content_json))
                    elif isinstance(paywalled_content_json, str): # 가끔 문자열로 들어올때가 있는데, 그 안에 또 json이 있음.
                        try:
                            nested_paywalled_content = json.loads(paywalled_content_json)
                            if isinstance(nested_paywalled_content, list):
                                article_text_parts.extend(self._extract_text_from_paywalled_content(nested_paywalled_content))
                        except json.JSONDecodeError:
                             print(f"[{self.site_name.upper()}] Failed to decode nested paywalledContent string for {article_url}")


                    # article_data를 찾으면 더 이상 apollo_state를 순회할 필요 없을 수 있음 (기사 하나당 하나의 Article:GUID)
                    # 하지만 다른 정보(Image 등)는 별도로 찾아야 할 수 있으므로 일단 계속 진행
            
            # 이미지 URL 추출
            if image_key and image_key in apollo_state and isinstance(apollo_state[image_key], dict):
                image_data = apollo_state[image_key]
                # 다양한 crop 버전 중 하나 선택 (예: 16:9 또는 원본)
                # crop({"ratio":"16:9"}) 형태의 키 또는 직접적인 url 필드
                if isinstance(image_data.get("url"), str): # 기본 URL 필드가 있다면 사용
                    main_image_url = image_data["url"]
                else: # crop된 URL 검색
                    for img_key, img_value in image_data.items():
                        if "crop(" in img_key and isinstance(img_value, dict) and isinstance(img_value.get("url"), str):
                            main_image_url = img_value["url"]
                            break # 첫번째 찾은 crop URL 사용
            
            # 만약 APOLLO_STATE에서 제목을 못가져왔다면 og:title 시도
            if article_title == original_title or not article_title:
                og_title_tag = soup.find('meta', property='og:title')
                if og_title_tag and og_title_tag.get('content'):
                    article_title = og_title_tag['content']
            
            # 만약 APOLLO_STATE에서 이미지를 못가져왔다면 og:image 시도
            if not main_image_url:
                og_image_tag = soup.find('meta', property='og:image')
                if og_image_tag and og_image_tag.get('content'):
                    main_image_url = og_image_tag['content']

        # JSON 파싱 실패 또는 데이터 부족 시, 기존 BeautifulSoup 기반 로직 (fallback)
        if not article_text_parts: # 본문을 JSON에서 전혀 못가져온 경우
            print(f"[{self.site_name.upper()}/{category.upper()}] Failed to get text from APOLLO_STATE for {article_url}. Falling back to HTML parsing.")
            
            # 제목 (JSON에서 못가져왔거나, 원래 제목 그대로라면 다시 시도)
            if article_title == original_title or not article_title:
                h1_tag = soup.find('h1', class_="responsive__HeadlineContainer-sc-3t8ix5-3 fOpTIx")
                if h1_tag: article_title = h1_tag.text.strip()
                elif not article_title: # 그래도 없으면 일반 h1
                    h1_tag = soup.find('h1')
                    if h1_tag: article_title = h1_tag.text.strip()

            # 이미지 (JSON에서 못가져왔다면 다시 시도)
            if not main_image_url:
                 # HTML에서 이미지 찾는 로직 (이전 버전의 것 간소화)
                img_tag_in_article = None
                article_main = soup.find('article', id='article-main')
                if article_main:
                    # figure, picture 태그 등 내부 탐색
                    figure_tag = article_main.find('figure')
                    if figure_tag: img_tag_in_article = figure_tag.find('img', src=True)
                    if not img_tag_in_article:
                        picture_tag = article_main.find('picture')
                        if picture_tag: img_tag_in_article = picture_tag.find('img', src=True)
                if img_tag_in_article:
                    main_image_url = urljoin(article_url, img_tag_in_article.get('src'))


            # 본문 컨테이너 (HTML에서 찾기)
            # <article class="responsive__BodyContainer-sc-15gvuj2-3 iRvTiE">
            # <div class="responsive__ArticleContent-sc-15gvuj2-8 kuowVf">
            body_container = soup.find('article', class_="responsive__BodyContainer-sc-15gvuj2-3")
            if not body_container:
                body_container = soup.find('div', class_="responsive__ArticleContent-sc-15gvuj2-8")
            
            if body_container:
                paragraphs = body_container.find_all('p') # 이 p태그들이 어떤 class를 가질지 불명확
                for p_tag in paragraphs:
                    text = p_tag.get_text(separator=' ', strip=True)
                    # 기본적인 필터링 (광고, 구독 유도 문구 등)
                    if text and len(text) > 30 and \
                       not re.search(r'(subscribe to continue|log in to continue|already a subscriber|view offer|copyright|topics:)', text, re.I):
                        article_text_parts.append(text)
        
        if not article_text_parts and not (apollo_state and any(key.startswith("Article:") for key in apollo_state)):
             # APOLLO_STATE도 없고, HTML에서도 본문을 못찾았으면, 아예 스크립트 없는 간단한 페이지일수도.
             # 최후의 수단: <article id="article-main"> 내부의 모든 p 태그
            article_main_fallback = soup.find('article', id='article-main')
            if article_main_fallback:
                paragraphs = article_main_fallback.find_all('p')
                for p_tag in paragraphs:
                    text = p_tag.get_text(separator=' ', strip=True)
                    if text and len(text) > 30 and \
                       not re.search(r'(subscribe to continue|log in to continue|already a subscriber|view offer|copyright|topics:)', text, re.I):
                        article_text_parts.append(text)


        if not article_text_parts:
            print(f"[{self.site_name.upper()}/{category.upper()}] No text found in article: {article_url} after all attempts.")
            # return None # 본문 없으면 None 반환할 수도 있으나, 제목/이미지만이라도 수집하려면 아래 유지

        full_article_text = '\n\n'.join(article_text_parts).strip()

        return {
            'url': article_url,
            'title': str(article_title).strip() if article_title else original_title.strip(),
            'main_image_url': str(main_image_url).strip() if main_image_url else None,
            'article_text': full_article_text,
            'source': "the times",
            'category': category
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