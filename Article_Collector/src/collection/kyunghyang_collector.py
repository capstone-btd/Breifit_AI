from .base_collector import BaseCollector
import aiohttp
from bs4 import BeautifulSoup
import yaml
import os
import asyncio
import re
import random
import urllib.parse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')

class KyunghyangCollector(BaseCollector):
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            site_config = config_data['sites']['kyunghyang']
            base_url = site_config['base_url']
        except Exception as e:
            print(f"[KyunghyangCollector] 설정 파일 로드 오류 ({config_path}): {e}. 기본 base_url을 사용합니다.")
            base_url = "https://www.khan.co.kr"
        super().__init__(site_name="kyunghyang", base_url=base_url)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        article_infos = []
        print(f"[{self.site_name}] Fetching links from {category_url}")
        try:
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # section.head 내의 메인 기사 및 서브 기사 링크 추출
            head_articles = soup.select('section.head article')
            for article_tag in head_articles:
                link_tag = article_tag.find('a', href=re.compile(r"^https://www.khan.co.kr/article/"))
                if link_tag:
                    href = link_tag.get('href')
                    title = link_tag.get('title', '').strip()
                    if not title: # title 속성이 없는 경우, a 태그 내부 텍스트 사용
                        title = link_tag.get_text(strip=True)
                    
                    if href and title:
                        # 상대 경로일 경우 base_url과 조합
                        if href.startswith('/'):
                            href = self.base_url + href
                        if href.startswith(self.base_url): # 해당 사이트의 기사인지 확인
                             article_infos.append({'title': title, 'url': href})

            # section.contents div.list 내의 기사 목록 추출
            list_articles = soup.select('section.contents div.list#recentList li article')
            for article_tag in list_articles:
                link_tag = article_tag.find('a', href=re.compile(r"^https://www.khan.co.kr/article/"))
                if link_tag:
                    href = link_tag.get('href')
                    title = link_tag.get('title', '').strip()
                    if not title: # title 속성이 없는 경우, a 태그 내부 텍스트 사용
                        title = link_tag.get_text(strip=True)

                    if href and title:
                        # 상대 경로일 경우 base_url과 조합
                        if href.startswith('/'):
                            href = self.base_url + href
                        if href.startswith(self.base_url): # 해당 사이트의 기사인지 확인
                            article_infos.append({'title': title, 'url': href})
            
            unique_articles = {info['url']: info for info in article_infos}.values()
            article_infos = list(unique_articles)
            print(f"[{self.site_name}] Found {len(article_infos)} news links from {category_url}")
        except Exception as e:
            print(f"[{self.site_name}] Error fetching or parsing links from {category_url}: {e}")
        return article_infos

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        await asyncio.sleep(random.uniform(1, 3))
        print(f"[{self.site_name.upper()}/{category.upper()}] 기사 내용 가져오기 시작: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=self.timeout_seconds) as response:
                response.raise_for_status()
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # TODO: 경향신문 기사 상세 페이지 구조에 맞는 선택자로 수정 필요
            title_tag = soup.select_one('h1.art_tit, h1.view_title, header h1.tit_subject')
            article_title = title_tag.get_text(strip=True) if title_tag else original_title
            
            article_body_tag = soup.select_one('div.art_body, div.art_cont, section.article_content')
            article_text = ""
            if article_body_tag:
                for el in article_body_tag.select('.related_article_gen, .kh_socialShare, .art_btm_box, script, style, iframe'):
                    el.decompose()
                paragraphs = article_body_tag.find_all('p', class_=lambda x: x != 'art_copyright' if x else True) # 저작권 문구 제외 시도
                if not paragraphs:
                    paragraphs = article_body_tag.find_all('p')
                for p in paragraphs:
                    article_text += p.get_text(strip=True) + "\n"
            if not article_text.strip(): article_text = original_title

            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            # TODO: og:image 없을 경우 대체 로직

            article_text_content = article_text.strip()
            if not article_text_content:
                print(f"[{self.site_name.upper()}/{category.upper()}] 기사 본문 내용을 추출하지 못했습니다: {article_url}")
                return None

            return {
                "url": article_url,
                "title": article_title,
                "main_image_url": main_image_url,
                "article_text": article_text_content,
                "source": self.site_name,
                "category": category
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
        키워드로 경향신문 기사를 검색합니다.
        - 검색 페이지의 실제 DOM 구조(카테고리별 그룹화)에 맞춰 '경향신문' 섹션만 파싱합니다.
        - 기본 파라미터: media=khan, section=1(제목), term=0(전체기간), sort=1(최신순), page=1
        - html 인자를 제공하면 네트워크 요청 없이 해당 HTML을 직접 파싱합니다.
        """
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = (
            f"https://search.khan.co.kr/?q={encoded_keyword}"
            f"&media=khan&section=1&term=0&sort=1&page=1"
        )
        
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
                articles: list[dict] = []
                
                # 광고 블록 제외를 위해 메인 리스트 영역 탐색
                # 카테고리별로 묶인 최상위 리스트: ul.list > li (각 li가 '경향신문', '스포츠경향' 등 섹션)
                khan_group = None
                for group in soup.select('ul.list > li'):
                    h3 = group.find('h3')
                    if h3 and '경향신문' in h3.get_text(strip=True):
                        khan_group = group
                        break
                if not khan_group:
                    # 폴백: 전체 문서에서 기사 카드 탐색
                    khan_group = soup
                
                # 섹션 내부 기사 li
                section_items = khan_group.select('ul > li')
                print(f"[{self.site_name}] '경향신문' 섹션 li 수집: {len(section_items)}개")
                
                # 링크 추출 및 기사 본문 수집(최대 20개)
                seen_urls: set[str] = set()
                for item in section_items:
                    # article 내부의 기사 앵커
                    link_tag = item.select_one(
                        'article a[href^="https://www.khan.co.kr/article/"], '
                        'article a[href^="/article/"]'
                    )
                    if not link_tag:
                        continue
                    article_url = link_tag.get('href')
                    if not article_url:
                        continue
                    if not article_url.startswith('http'):
                        article_url = urllib.parse.urljoin(self.base_url + '/', article_url)
                    # 경향신문 본사 기사만 수집
                    if not article_url.startswith(self.base_url + '/article/'):
                        continue
                    if article_url in seen_urls:
                        continue
                    seen_urls.add(article_url)
                    
                    # 제목: a@title 우선, 없으면 텍스트
                    title = link_tag.get('title') or link_tag.get_text(strip=True)
                    if not title:
                        continue
                    
                    article_data = await self.fetch_article_content(session, article_url, title, 'search')
                    if article_data:
                        articles.append(article_data)
                    if len(articles) >= 20:
                        break
                
                print(f"[{self.site_name}] 키워드 '{keyword}'로 {len(articles)}개 기사 수집 완료")
                return articles
                
            except Exception as e:
                print(f"[{self.site_name}] 키워드 '{keyword}' 검색 중 오류: {e}")
                return []

# 테스트 코드 (main 함수) 수정
# ... existing code ... 