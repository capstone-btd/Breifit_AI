from .base_collector import BaseCollector
import aiohttp
from bs4 import BeautifulSoup
import yaml
import os
import asyncio
import re
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')

class ChosunCollector(BaseCollector):
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            site_config = config_data['sites']['chosun']
            base_url = site_config['base_url']
        except Exception as e:
            print(f"[ChosunCollector] 설정 파일 로드 오류 ({config_path}): {e}. 기본 base_url을 사용합니다.")
            base_url = "https://www.chosun.com"
        super().__init__(site_name="chosun", base_url=base_url)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        article_infos = []
        print(f"[{self.site_name}] Fetching links from {category_url}")
        try:
            await asyncio.sleep(random.uniform(1, 3)) # 1~3초 랜덤 대기
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 조선일보 카테고리 페이지 구조에 맞는 선택자로 수정
            # story-card-container 내부의 a 태그 (headline)
            article_cards = soup.select('div.story-card-container')
            for card in article_cards:
                link_tag = card.select_one('a.story-card__headline')
                if link_tag:
                    href = link_tag.get('href')
                    title_tag = link_tag.select_one('span')
                    title = title_tag.get_text(strip=True) if title_tag else link_tag.get_text(strip=True)

                    if href and title:
                        # 상대 경로일 경우 절대 경로로 변환
                        if href.startswith('/'):
                            href = self.base_url + href
                        
                        # 해당 사이트의 기사인지 확인 (base_url로 시작하는지)
                        if href.startswith(self.base_url):
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
            async with session.get(article_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목 (여러 가능한 선택자 조합)
            title_selectors = [
                'h1.article_title', 
                'h1.news_title', 
                'header h1',
                'h1[class*="title"]', # 클래스에 title을 포함하는 h1
                'div[class*="article-header"] h1' # article-header 내부의 h1
            ]
            article_title = original_title
            for selector in title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag and title_tag.get_text(strip=True):
                    article_title = title_tag.get_text(strip=True)
                    break
            
            # 본문 (여러 가능한 선택자 조합)
            # 우선적으로 새로운 HTML 구조에 맞는 선택자 시도
            article_text = ""
            article_body_tag = soup.select_one('section.article-body[itemprop="articleBody"]')
            
            if article_body_tag:
                # 불필요한 태그 제거 (광고, 관련기사, 이미지 캡션 등)
                for unwanted_tag in article_body_tag.select('div.arcad-wrapper, div.dfpAd, div.article-body__content-rawhtml, div#a22, style, script, aside, .related_news, .ad_wrap, figure.article-body__content-image'):
                    unwanted_tag.decompose()
                
                # 특정 클래스를 가진 p 태그들만 선택
                paragraphs = article_body_tag.select('p.article-body__content.article-body__content-text')
                for p in paragraphs:
                    article_text += p.get_text(strip=True) + "\n"

            # 새로운 선택자로 본문을 찾지 못한 경우 기존 로직 수행
            if not article_text.strip():
                body_selectors = [
                    'section.article_body', 
                    'div.article_body', 
                    'div.news_text',
                    'article[class*="article-body"]', 
                    'div[itemprop="articleBody"]' 
                ]
                article_body_tag_old = None
                for selector in body_selectors:
                    article_body_tag_old = soup.select_one(selector)
                    if article_body_tag_old:
                        break
                
                if article_body_tag_old:
                    # 불필요한 태그 제거 (광고, 관련기사, 이미지 캡션 등)
                    for unwanted_tag in article_body_tag_old.select('div.arcad-wrapper, div.dfpAd, div.article-body__content-rawhtml, div#a22, style, script, aside, .related_news, .ad_wrap, figure.article-body__content-image'):
                        unwanted_tag.decompose()

                    paragraphs = article_body_tag_old.find_all('p', recursive=True) 
                    if not paragraphs: 
                        temp_text = article_body_tag_old.get_text(separator="\n", strip=True)
                        if temp_text : paragraphs = [BeautifulSoup(f'<p>{line}</p>', 'html.parser').p for line in temp_text.split('\n') if line.strip()]

                    for p in paragraphs:
                        if p: 
                             article_text += p.get_text(strip=True) + "\n"
            
            if not article_text.strip(): 
                # 최후의 수단: body 전체에서 텍스트 추출 (매우 비효율적일 수 있음)
                print(f"[{self.site_name}] Warning: Could not find specific article body for {article_url}. Trying to extract from body.")
                body_tag = soup.find('body')
                if body_tag:
                    article_text = body_tag.get_text(separator="\n", strip=True)
                if not article_text.strip(): # 그래도 없으면 원래 제목이라도 넣음
                     article_text = original_title

            # 대표 이미지
            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            else:
                # 본문 내 첫번째 이미지 시도
                if article_body_tag:
                    img_tag = article_body_tag.find('img')
                    if img_tag and img_tag.get('src'):
                        main_image_url = img_tag['src']
                        if main_image_url.startswith('//'):
                            main_image_url = 'https:' + main_image_url
                        elif main_image_url.startswith('/'):
                             main_image_url = self.base_url + main_image_url

            if not article_text.strip():
                print(f"[{self.site_name.upper()}/{category.upper()}] 기사 본문 내용을 추출하지 못했습니다: {article_url}")
                return None

            return {
                "url": article_url,
                "title": article_title,
                "main_image_url": main_image_url,
                "article_text": article_text.strip(),
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

    def get_news_urls_for_category(self, category_url):
        """
        카테고리 페이지에서 개별 뉴스 기사 URL을 수집합니다.
        이 메소드는 조선일보 웹사이트의 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 조선일보 카테고리 페이지 구조에 맞춰 뉴스 URL 추출 로직 구현
        news_urls = []
        print(f"[{self.name}] Extracting news URLs from {category_url} (not implemented yet)")
        return news_urls

    def extract_article_content(self, news_url):
        """
        개별 뉴스 기사 URL에서 제목, 본문, 작성일 등을 추출합니다.
        이 메소드는 조선일보 웹사이트의 기사 페이지 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 조선일보 기사 페이지 구조에 맞춰 기사 내용 추출 로직 구현
        print(f"[{self.name}] Extracting content from {news_url} (not implemented yet)")
        return None # 실제 구현 필요 