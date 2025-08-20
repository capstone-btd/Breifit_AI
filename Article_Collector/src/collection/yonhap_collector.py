from .base_collector import BaseCollector
import aiohttp # aiohttp.ClientSession 사용을 위해 추가
from bs4 import BeautifulSoup
import yaml # 설정 파일 로드를 위해 추가
import os # 파일 경로 처리를 위해 추가
import asyncio
import random
import urllib.parse

# 프로젝트 루트 경로 설정 (BaseCollector와 유사하게)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')

class YonhapCollector(BaseCollector):
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        # 설정 파일에서 base_url 로드
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            site_config = config_data['sites']['yonhap']
            base_url = site_config['base_url']
        except Exception as e:
            print(f"[YonhapCollector] 설정 파일 로드 오류 ({config_path}): {e}. 기본 base_url을 사용합니다.")
            base_url = "https://www.yna.co.kr" # Fallback
        
        super().__init__(site_name="yonhap", base_url=base_url)
        self.headers = { # BaseCollector에 headers가 없다면 여기서 정의
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        """
        카테고리 페이지에서 개별 뉴스 기사 URL과 제목을 수집합니다.
        """
        article_infos = []
        print(f"[{self.site_name}] Fetching links from {category_url}") # 콘솔 로그 추가
        try:
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            # 제공된 HTML 구조에 기반한 선택자 수정
            article_list_container = soup.select_one('div.list-type212 ul.list01')

            if article_list_container:
                article_items = article_list_container.find_all('li', recursive=False) # 직접적인 li 자식들만
                for item in article_items:
                    link_tag = item.select_one('div.news-con strong.tit-wrap a.tit-news')
                    if link_tag:
                        href = link_tag.get('href')
                        title_span = link_tag.find('span', class_='title01')
                        title = title_span.get_text(strip=True) if title_span else link_tag.get_text(strip=True)

                        if href and title:
                            # 연합뉴스 기사 URL은 보통 /view/AKR... 형태를 가집니다.
                            # 전체 URL로 변환하고, 유효성을 검사합니다.
                            if not href.startswith('http'):
                                full_url = self.base_url + href if href.startswith('/') else self.base_url + '/' + href
                            else:
                                full_url = href
                            
                            # 해당 사이트의 기사인지, 유효한 기사 URL 형식인지 확인
                            if full_url.startswith(self.base_url) and '/view/AKR' in full_url:
                                article_infos.append({'title': title, 'url': full_url})
            
            # 중복 제거 (URL 기준)
            unique_articles = {info['url']: info for info in article_infos}.values()
            article_infos = list(unique_articles)
            print(f"[{self.site_name}] Found {len(article_infos)} news links from {category_url}") # news URLs -> news links

        except aiohttp.ClientError as e:
            print(f"[{self.site_name}] ClientError fetching links from {category_url}: {e}") # category -> links from
        except asyncio.TimeoutError:
            print(f"[{self.site_name}] Timeout fetching links from {category_url}") # category -> links from
        except Exception as e:
            print(f"[{self.site_name}] Error parsing links from {category_url}: {e}") # category -> links from
            
        return article_infos

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        await asyncio.sleep(random.uniform(1, 3))
        print(f"[{self.site_name.upper()}/{category.upper()}] 기사 내용 가져오기 시작: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=self.timeout_seconds) as response:
                response.raise_for_status()
                html_content = await response.text()
            
            soup = BeautifulSoup(html_content, 'html.parser')

            title_tag = soup.find('h1', class_='title') # 연합뉴스 제목 선택자 예시
            article_title = title_tag.get_text(strip=True) if title_tag else original_title

            # 본문 추출 (선택자 확인 필요)
            article_body_tag = soup.find('div', class_='story-news') 
            if not article_body_tag:
                 article_body_tag = soup.find('article', class_='story-news') # 다른 가능한 본문 컨테이너
            
            article_text = ""
            if article_body_tag:
                paragraphs = article_body_tag.find_all('p', recursive=False) # 직계 p 태그 우선, 너무 깊게 들어가지 않도록
                if not paragraphs: # 직계 p가 없으면 모든 p 탐색
                    paragraphs = article_body_tag.find_all('p')
                for p in paragraphs:
                    article_text += p.get_text(strip=True) + "\n"
            else:
                # 대체 본문 검색 로직 (예: class가 article_txt, content_txt 등)
                alt_body = soup.select_one(".article_txt, .content_txt, #articleBody, #newsEndContents")
                if alt_body:
                    article_text = alt_body.get_text(separator="\n", strip=True)

            if not article_text.strip(): # 본문이 비었으면 original_title이라도 넣어줌 (추후 수정)
                print(f"[{self.site_name.upper()}/{category.upper()}] 본문 내용 없음: {article_url}")
                article_text = original_title # 임시 처리

            # 연합뉴스 기사 본문 특별 처리
            # 1. '제보는' 이후 내용 제거
            report_index = article_text.rfind('제보는')
            if report_index != -1:
                article_text = article_text[:report_index]

            # 2. 기자 정보 이전 내용 제거
            reporter_index = article_text.find('기자')
            if reporter_index != -1:
                equals_index = article_text.find('=', reporter_index)
                if equals_index != -1:
                    article_text = article_text[equals_index + 1:].lstrip()

            # 대표 이미지 URL 추출 (선택자 확인 필요)
            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            else:
                # 기사 본문 내 첫번째 이미지 등 대체 로직
                if article_body_tag:
                    img_tag = article_body_tag.find('img')
                    if img_tag and img_tag.get('src'):
                        main_image_url = img_tag['src']
                        if main_image_url.startswith('//'):
                            main_image_url = 'https:' + main_image_url
                        elif not main_image_url.startswith('http'):
                             main_image_url = self.base_url + main_image_url if main_image_url.startswith('/') else self.base_url + "/" + main_image_url
            
            # 작성일 추출 (선택자 및 형식 변환 필요) - BaseCollector는 published_at을 요구하지 않음.
            # time_tag = soup.select_one('p.update-time, span.poto_w_time, span.txt-time')
            # published_at_text = time_tag.get_text(strip=True) if time_tag else "N/A"
            # TODO: published_at_text를 표준 형식(YYYY-MM-DD HH:MM:SS)으로 변환

            print(f"[{self.site_name.upper()}/{category.upper()}] Extracted content from {article_url}: Title='{article_title}'")
            return {
                'url': article_url,
                'title': article_title.strip(),
                'main_image_url': main_image_url,
                'article_text': article_text.strip(),
                'source': "yonhap",
                'category': category
            }

        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}/{category.upper()}] 기사 페이지 로딩 시간 초과: {article_url}")
            return None
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}/{category.upper()}] 기사 페이지 로딩 중 ClientError: {e}, URL: {article_url}")
            return None
        except Exception as e:
            print(f"[{self.site_name.upper()}/{category.upper()}] HTML 가져오는 중 알 수 없는 오류 ({article_url}): {e}")
            return None

    async def search_by_keyword(self, keyword: str, html: str | None = None) -> list[dict]:
        """
        키워드로 연합뉴스 기사를 검색합니다.
        - 검색 페이지의 실제 DOM 구조에 맞춰 '뉴스' 섹션(box-serp01-news) 내 기사만 수집합니다.
        - 기본 파라미터: ctype=A(뉴스)
        - html 인자를 제공하면 네트워크 호출 없이 해당 HTML을 직접 파싱합니다.
        """
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.yna.co.kr/search/index?query={encoded_keyword}&ctype=A"
        
        async with aiohttp.ClientSession() as session:
            try:
                if html is None:
                    print(f"[{self.site_name}] 키워드 '{keyword}' 검색: {search_url}")
                    async with session.get(search_url, headers=self.headers, timeout=30) as response:
                        response.raise_for_status()
                        html_content = await response.text()
                else:
                    html_content = html
                    print(f"[{self.site_name}] 제공된 HTML로 키워드 '{keyword}' 검색 파싱 수행")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                # '뉴스' 섹션 선택 (box-serp01-news)
                news_section = soup.select_one('section.box-serp01-news')
                if not news_section:
                    news_section = soup
                
                # li 아이템 기준으로 앵커 추출
                li_items = news_section.select('div.list-type501 ul.list01 > li')
                if not li_items:
                    li_items = news_section.select('ul.list01 > li')
                print(f"[{self.site_name}] 검색 리스트 li 수집: {len(li_items)}개")
                
                articles: list[dict] = []
                seen_urls: set[str] = set()
                
                for li in li_items:
                    anchor = li.select_one('div.item-box01 > a, a[href^="/view/"], a[href^="https://www.yna.co.kr/view/"]')
                    if not anchor:
                        continue
                    href = anchor.get('href')
                    if not href:
                        continue
                    if not href.startswith('http'):
                        article_url = urllib.parse.urljoin(self.base_url + '/', href)
                    else:
                        article_url = href
                    
                    # fetch_article_links와 동일한 방식으로 URL 유효성 검사
                    if not (article_url.startswith(self.base_url) and '/view/AKR' in article_url):
                        continue
                    if article_url in seen_urls:
                        continue
                    seen_urls.add(article_url)
                    
                    title_tag = anchor.select_one('span.title01')
                    title_text = title_tag.get_text(strip=True) if title_tag else anchor.get_text(strip=True)
                    if not title_text:
                        continue
                    
                    article_data = await self.fetch_article_content(session, article_url, title_text, 'search')
                    if article_data:
                        articles.append(article_data)
                    if len(articles) >= 20:
                        break
                
                print(f"[{self.site_name}] 키워드 '{keyword}'로 {len(articles)}개 기사 수집 완료")
                return articles
                
            except Exception as e:
                print(f"[{self.site_name}] 키워드 '{keyword}' 검색 중 오류: {e}")
                return []

    # is_valid_news_url 메소드는 BaseCollector에 없으므로 여기서 사용하지 않거나, 
    # 필요시 BaseCollector에 추가 또는 여기서 별도 로직으로 활용.
    # def is_valid_news_url(self, url):
    #     return '/view/AKR' in url 