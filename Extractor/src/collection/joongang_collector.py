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

class JoongangCollector(BaseCollector):
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            site_config = config_data['sites']['joongang']
            base_url = site_config['base_url']
        except Exception as e:
            print(f"[JoongangCollector] 설정 파일 로드 오류 ({config_path}): {e}. 기본 base_url을 사용합니다.")
            base_url = "https://www.joongang.co.kr"
        super().__init__(site_name="joongang", base_url=base_url)
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
            
            article_url_pattern = f"{self.base_url}/article/"
            # Uses .card selector to find articles in showcase, most viewed, and latest lists.
            # Selects <a> tags whose href starts with the article_url_pattern.
            link_tags = soup.select(f'.card a[href^="{article_url_pattern}"]')

            for link_tag in link_tags:
                href = link_tag.get('href')
                title = link_tag.get_text(strip=True)
                if not title:
                    img_tag = link_tag.find('img')
                    if img_tag and img_tag.get('alt'):
                        title = img_tag.get('alt').strip()
                if not title: # Fallback for title from href
                    title_parts = [part for part in href.split('/') if part]
                    if title_parts:
                        slug_part = title_parts[-1].split('?')[0] # Remove query params
                        title = slug_part.replace('-', ' ').replace('_', ' ')
                        title = ' '.join(word.capitalize() for word in title.split()) # Capitalize for readability

                if href and title and href.startswith(self.base_url): # Ensure it's a valid article link from the same domain
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
            
            # TODO: 중앙일보 기사 상세 페이지 구조에 맞는 선택자로 수정 필요
            title_tag = soup.select_one('h1.card_title, h1.title, article header h1')
            article_title = title_tag.get_text(strip=True) if title_tag else original_title
            
            article_body_tag = soup.select_one('div#article_body, div.article_content, section.article_body')
            article_text = ""
            if article_body_tag:
                paragraphs = article_body_tag.find_all('p', recursive=False)
                if not paragraphs:
                    paragraphs = article_body_tag.find_all('p')
                for p in paragraphs:
                    article_text += p.get_text(strip=True) + "\n"
            if not article_text.strip(): article_text = original_title

            main_image_url = None
            # og_image_tag = soup.find('meta', property='og:image')
            # if og_image_tag and og_image_tag.get('content'):
            #     main_image_url = og_image_tag['content']
            
            if not main_image_url:
                image_div = soup.select_one('div.image')
                if image_div:
                    img_tag = image_div.find('img')
                    if img_tag and img_tag.get('data-src'):
                        main_image_url = img_tag['data-src']
            
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
        이 메소드는 중앙일보 웹사이트의 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 중앙일보 카테고리 페이지 구조에 맞춰 뉴스 URL 추출 로직 구현
        news_urls = []
        print(f"[{self.name}] Extracting news URLs from {category_url} (not implemented yet)")
        return news_urls

    def extract_article_content(self, news_url):
        """
        개별 뉴스 기사 URL에서 제목, 본문, 작성일 등을 추출합니다.
        이 메소드는 중앙일보 웹사이트의 기사 페이지 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 중앙일보 기사 페이지 구조에 맞춰 기사 내용 추출 로직 구현
        print(f"[{self.name}] Extracting content from {news_url} (not implemented yet)")
        return None # 실제 구현 필요 