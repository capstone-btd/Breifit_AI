import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin # 상대 URL을 절대 URL로 변환하기 위함
import re

from .base_collector import BaseCollector
# from ..utils.file_helper import slugify # 필요시 주석 해제

class BBCCollector(BaseCollector):
    def __init__(self):
        super().__init__(site_name="bbc", base_url="https://www.bbc.com")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-GB,en;q=0.9' # 영국 영어 콘텐츠 우선 요청
        }
        # BBC는 특정 쿠키나 추가 헤더가 필요할 수 있습니다 (예: 지역 설정). 필요시 추가합니다.

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        await asyncio.sleep(2) # 요청 전 2초 지연
        print(f"[{self.site_name.upper()}] {category_url} 에서 기사 목록을 가져오는 중...")
        article_links = []
        try:
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status() # 200이 아닌 경우 예외 발생
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] 메인 페이지 로딩 시간 초과: {category_url}")
            return []
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] 메인 페이지 로딩 중 ClientError 발생: {e}, URL: {category_url}")
            return []
        except Exception as e:
            print(f"[{self.site_name.upper()}] HTML 가져오는 중 알 수 없는 오류 ({category_url}): {e}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        links_found = set() # 중복 URL 방지

        # 1. data-indexcard="true" 속성을 가진 카드에서 링크 추출 (가장 우선적)
        cards = soup.find_all('div', attrs={'data-indexcard': 'true'})
        if not cards:
            # 대체 선택자: section 태그 내부의 일반적인 카드 구조 (class에 card, promo, item 등 포함)
            sections = soup.find_all('section', attrs={'data-testid': re.compile(r'section-outer', re.I)})
            if not sections: # 최상위 섹션도 없으면, body 전체에서 카드 패턴 탐색
                sections = [soup.body]

            for section in sections:
                if section: # section이 None이 아닌 경우에만 find_all 호출
                    # 일반적인 카드형태의 div나 li (class에 item, card, promo, post 등 포함)
                    potential_cards = section.find_all(['div', 'li'], class_=re.compile(r"(item|card|promo|post|tout)", re.I))
                    cards.extend(potential_cards)
        
        # cards가 여전히 비어있다면, 더 넓은 범위로 검색 (예: gs-c-promo, lx-stream-post 등 BBC 고유 패턴)
        if not cards:
            cards.extend(soup.find_all('div', class_=re.compile(r"gs-c-promo|lx-stream-post", re.I)))


        for card in cards:
            link_tag = card.find('a', attrs={'data-testid': 'internal-link'}, href=True)
            if not link_tag: # data-testid="internal-link"가 없는 경우, 일반적인 링크 탐색
                # 링크가 제목 태그를 감싸고 있는 경우도 있고, 카드 내부에 직접 있는 경우도 고려
                # headline을 포함한 태그 내의 첫번째 a 태그
                headline_area = card.find(attrs={'data-testid': re.compile(r'card-headline|promo-headline', re.I)})
                if headline_area:
                    link_tag = headline_area.find_parent('a', href=True) # 부모에서 a 찾기
                    if not link_tag: # 부모에 없으면 자식에서 a 찾기
                         link_tag = headline_area.find('a', href=True)
                
                if not link_tag: # headline 영역에서 못찾았으면 카드 전체에서 첫번째 링크
                    link_tag = card.find('a', href=True)
            
            if link_tag:
                href = link_tag.get('href')
                # 제목 추출
                title_tag = card.find(re.compile(r'h[1-6]|p'), attrs={'data-testid': 'card-headline'})
                if not title_tag: # data-testid가 없는 경우, 클래스명으로 시도
                    title_tag = card.find(re.compile(r'h[1-6]|p'), class_=re.compile(r".*(title|headline|heading|summary).*", re.IGNORECASE))
                
                title_text = title_tag.text.strip() if title_tag else link_tag.text.strip() # 최후의 수단으로 링크 텍스트

                if href and title_text and len(title_text) > 5 and href not in links_found: # 제목이 너무 짧으면 제외
                    full_url = urljoin(self.base_url, href)
                    
                    # bbc.com 또는 bbc.co.uk 도메인인지 확인
                    if full_url.startswith("https://www.bbc.com") or full_url.startswith("https://www.bbc.co.uk"):
                        # 이미 수집된 URL이 아니며, 뉴스 기사로 보이는 URL 패턴 (광고나 섹션 링크 제외)
                        # 예: /newsround/60000000, /sport/football/50000000
                        # 제외할 패턴: /sounds, /iplayer, /weather, /bitesize, /food/recipes/ 등
                        if not re.match(r".*(\/sounds|\/iplayer|\/weather|\/bitesize|\/food|\/travel\/(\w{2})\/information|\/programmes|\/collections).*", full_url):
                            # live 페이지도 제외
                            if "/live/" not in full_url:
                                article_links.append({'title': title_text, 'url': full_url})
                                links_found.add(href)
                                links_found.add(full_url) # 정규화된 URL도 추가

        # 중복 제거 (최종)
        final_links = []
        final_urls = set()
        for link_info in article_links:
            if link_info['url'] not in final_urls:
                final_links.append(link_info)
                final_urls.add(link_info['url'])
        article_links = final_links

        if not article_links:
            print(f"[{self.site_name.upper()}] {category_url} 에서 기사 링크를 찾지 못했습니다. HTML 구조 확인 및 선택자 수정이 필요합니다.")
        else:
            print(f"[{self.site_name.upper()}] 총 {len(article_links)}개의 고유한 기사 링크를 찾았습니다 ({category_url}).")
        return article_links

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        await asyncio.sleep(2) # 요청 전 2초 지연
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

        # 1. 메타 태그에서 제목 추출
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            article_title = og_title['content']
        else:
            # 2. h1 태그에서 제목 추출 (id, class 기반)
            title_tag = soup.find('h1', id='main-heading')
            if not title_tag:
                title_tag = soup.find('h1', class_=re.compile(r'.*(ArticleTitle|HeadlineText|PageTitle|StoryHeadline).*', re.I))
            if not title_tag: # 좀 더 일반적인 h1
                 title_tag = soup.find('h1')
            if title_tag:
                article_title = title_tag.text.strip()

        # 대표 이미지 추출
        # 1. OpenGraph 태그
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            main_image_url = og_image['content']
        else:
            # 2. 기사 본문 내의 주요 이미지 (figure > img)
            #    ssrcss- 스타일의 동적 클래스를 피하기 위해 태그 구조에 집중
            article_tag = soup.find('article')
            if article_tag:
                main_image_container = article_tag.find('figure', recursive=False) # article 직계 자식 figure
                if main_image_container:
                    img_tag = main_image_container.find('img', src=True)
                    if img_tag:
                        main_image_url = urljoin(article_url, img_tag.get('src'))
            
            if not main_image_url: # article 내에 없으면 body 전체에서 첫번째 figure > img
                main_image_container = soup.find('figure')
                if main_image_container:
                    img_tag = main_image_container.find('img', src=True)
                    if img_tag:
                         main_image_url = urljoin(article_url, img_tag.get('src'))


        # 본문 추출
        # 1. <article> 태그를 최우선으로 탐색
        article_body = soup.find('article')
        
        # 2. <article> 태그가 없다면, 주요 콘텐츠 영역으로 보이는 div 탐색
        if not article_body:
            # role="main" 또는 id="main-content" 등
            main_content_divs = soup.find_all('div', attrs={'role': 'main'})
            if not main_content_divs:
                main_content_divs = soup.find_all('div', id=re.compile(r"main-content|content|story-body", re.I))
            
            for main_div in main_content_divs:
                # data-component="text-block" 등을 찾기 전에, main_div 자체가 본문일 가능성 확인
                # 불필요한 자식 태그 (광고, 추천, 공유 버튼 등) 제외
                text_holding_divs = main_div.find_all('div', attrs={'data-component': re.compile(r"text-block|paragraph", re.I)})
                if text_holding_divs:
                    article_body = main_div # 이 main_div를 본문 컨테이너로 간주
                    break
                # text-block이 없으면, main_div 내부의 p 태그들을 직접 수집할 수도 있음
                # 하지만 너무 광범위하므로 우선은 text-block 기반으로 시도

        # 본문 컨테이너 (article_body)를 찾았으면, 그 안에서 텍스트 조각 수집
        if article_body:
            # 제외할 data-component 값들
            excluded_data_components = [
                "image-block", "video-block", "audio-block", "slideshow-block",
                "links-block", "related-items-block", "timestamp-block",
                "topic-list", "unordered-list-block", "ordered-list-block", # 너무 일반적일 수 있으니 주의
                "share-tools-block", "byline-block", "consent-banner",
                "mpu-block", "advertisement-block", "social-embed-block",
                "guide-block", "story-highlights-block", "podcast-promo-block",
                "fact-check-block", "pull-quote-block", "crosshead-block" # crosshead는 소제목
            ]
            # 제외할 태그들
            excluded_tags = ['aside', 'nav', 'footer', 'figure', 'figcaption', 'script', 'style', 'form', 'iframe']
            # 제외할 클래스 패턴 (광고, 소셜 등)
            excluded_class_patterns = re.compile(r"(advert|social|related|share|promo|banner|caption|meta)", re.I)

            # 1. data-component="text-block" 또는 유사한 div 블록들을 우선 수집
            text_blocks = article_body.find_all('div', attrs={'data-component': re.compile(r"text-block|paragraph", re.I)})
            if text_blocks:
                for block in text_blocks:
                    # 블록 자체가 제외 대상 태그의 자손인지 확인
                    if any(parent.name in excluded_tags or (parent.get('data-component') and parent.get('data-component') in excluded_data_components) for parent in block.parents if parent != article_body):
                        continue
                    
                    block_text = block.get_text(separator=' ', strip=True)
                    if block_text:
                        article_text_parts.append(block_text)
            
            # 2. text-block 방식이 아니거나 추가로 p 태그들을 수집 (위에서 못 걸러낸 경우)
            if not article_text_parts or len("".join(article_text_parts)) < 200: # 너무 짧으면 p태그도 탐색
                paragraphs = article_body.find_all('p')
                for p in paragraphs:
                    # 부모 중에 제외할 태그나 data-component가 있는지 확인
                    is_excluded = False
                    for parent in p.parents:
                        if parent == article_body: # article_body 직전까지만 검사
                            break
                        if parent.name in excluded_tags:
                            is_excluded = True
                            break
                        parent_data_component = parent.get('data-component')
                        if parent_data_component and parent_data_component in excluded_data_components:
                            is_excluded = True
                            break
                        # 부모의 클래스 확인
                        parent_class = parent.get('class', [])
                        if any(excluded_class_patterns.search(cls_name) for cls_name in parent_class):
                            is_excluded = True
                            break
                    if is_excluded:
                        continue

                    # p 태그 자체의 클래스 확인
                    p_class = p.get('class', [])
                    if any(excluded_class_patterns.search(cls_name) for cls_name in p_class):
                        continue
                    
                    # data-testid 또는 특정 역할이 있는 p 태그 제외
                    if p.get('data-testid') and ('card-description' in p.get('data-testid') or 'timestamp' in p.get('data-testid')):
                        continue

                    text = p.get_text(separator=' ', strip=True)
                    if text:
                        article_text_parts.append(text)
        else:
            print(f"[{self.site_name.upper()}] 기사 본문 컨테이너(<article> 또는 주요 div)를 찾지 못했습니다: {article_url}")

        # 중복 제거 및 정리
        unique_text_parts = []
        seen_texts = set()
        for part in article_text_parts:
            if part and part not in seen_texts:
                unique_text_parts.append(part)
                seen_texts.add(part)
        
        body_content = "\n\n".join(unique_text_parts)

        # 본문이 너무 짧으면, 최후의 수단으로 <article> 또는 main content div의 전체 텍스트 시도 (정제는 덜 됨)
        if len(body_content) < 100 : # 임계값 (너무 짧은 본문)
            print(f"[{self.site_name.upper()}] 추출된 본문이 너무 짧습니다. ({len(body_content)}자). 대체 로직 시도 중...: {article_url}")
            final_attempt_container = soup.find('article') or soup.find('div', attrs={'role': 'main'})
            if final_attempt_container:
                # 모든 script, style, aside, nav, footer, figure(이미지 캡션 없는) 제거
                for unwanted_tag in final_attempt_container.find_all(['script', 'style', 'aside', 'nav', 'footer', 'form', 'iframe']):
                    unwanted_tag.decompose()
                # 광고/관련 콘텐츠 섹션으로 보이는 것들 제거 (좀 더 공격적)
                for section in final_attempt_container.find_all(['div', 'section'], class_=excluded_class_patterns):
                    section.decompose()
                for section in final_attempt_container.find_all(['div', 'section'], attrs={'data-component': excluded_data_components}):
                    section.decompose()
                
                body_content = final_attempt_container.get_text(separator="\n\n", strip=True)


        if not body_content:
            print(f"[{self.site_name.upper()}/{category.upper()}] 기사 본문 내용을 추출하지 못했습니다: {article_url}. HTML 구조를 확인하세요.")
            return None

        return {
            "url": article_url,
            "title": article_title,
            "main_image_url": main_image_url,
            "article_text": body_content,
            "source": self.site_name,
            "category": category
        }

if __name__ == '__main__':
    # BBCCollector 테스트를 위한 간단한 코드
    # python -m src.collection.bbc_collector 로 실행
    async def test_bbc_category(collector: BBCCollector, category_name_display: str, category_path: str):
        print(f"\n--- {collector.site_name.upper()} {category_name_display.upper()} 기사 수집 테스트 ---")
        
        # collect_by_category 메소드는 base_url과 category_path_segment를 조합하여 URL을 만듭니다.
        # 예: https://www.bbc.com/news
        # category_path가 이미 전체 URL이면 is_full_url=True로 설정 필요
        is_full_url = category_path.startswith("http")
        if is_full_url:
            target_url = category_path
        else:
            target_url = urljoin(collector.base_url, category_path)

        # fetch_article_links를 직접 호출
        async with aiohttp.ClientSession() as session:
            links = await collector.fetch_article_links(session, target_url)
        
        collected_articles = []
        if links:
            print(f"[{collector.site_name.upper()}/{category_name_display.upper()}] 링크 {len(links)}개 발견. 첫 2개 기사 내용 수집 시도:")
            async with aiohttp.ClientSession() as session:
                tasks = []
                for link_info in links[:2]: # 처음 2개만 테스트
                    tasks.append(collector.fetch_article_content(session, link_info['url'], link_info['title'], category_name_display))
                
                results = await asyncio.gather(*tasks)
                collected_articles = [res for res in results if res]

        if collected_articles:
            print(f"[{collector.site_name.upper()}/{category_name_display.upper()}] 테스트로 수집된 기사 ({len(collected_articles)}개):")
            for i, article in enumerate(collected_articles): # 처음 2개만 출력
                print(f"  {i+1}. 제목: {article.get('title', 'N/A')}")
                print(f"     URL: {article.get('url', 'N/A')}")
                print(f"     카테고리: {article.get('category', 'N/A')}")
                print(f"     이미지: {article.get('main_image_url', 'N/A')}")
                text_snippet = article.get('article_text', '')[:150].replace('\n', ' ')
                print(f"     본문 일부: {text_snippet}...")
        else:
            print(f"[{collector.site_name.upper()}/{category_name_display.upper()}] 해당 카테고리에서 기사를 수집하지 못했습니다. HTML 구조 및 선택자를 확인하세요.")