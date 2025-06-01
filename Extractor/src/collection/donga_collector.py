from .base_collector import BaseCollector
import aiohttp
from bs4 import BeautifulSoup
import yaml
import os
import asyncio
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'configs', 'news_sites.yaml')

class DongaCollector(BaseCollector):
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            site_config = config_data['sites']['donga']
            base_url = site_config['base_url']
        except Exception as e:
            print(f"[DongaCollector] 설정 파일 로드 오류 ({config_path}): {e}. 기본 base_url을 사용합니다.")
            base_url = "https://www.donga.com"
        super().__init__(site_name="donga", base_url=base_url)
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
            
            # 동아일보 카테고리 페이지 구조에 맞는 선택자로 수정
            # 기사 카드는 article.news_card 이고, 제목과 링크는 div.news_body hX.tit a 에 있음
            link_tags = soup.select('article.news_card div.news_body h2.tit a, article.news_card div.news_body h3.tit a, article.news_card div.news_body h4.tit a')
            
            for link_tag in link_tags:
                href = link_tag.get('href')
                title = link_tag.get_text(strip=True)

                if href and title and href.startswith(self.base_url):
                    # 상대 경로인 경우 절대 경로로 변환 (이미 절대 경로이지만, 만약을 위해)
                    if href.startswith('/'):
                        href = self.base_url + href
                    article_infos.append({'title': title, 'url': href})
            
            unique_articles = {info['url']: info for info in article_infos}.values()
            article_infos = list(unique_articles)
            print(f"[{self.site_name}] Found {len(article_infos)} news links from {category_url}")
        except Exception as e:
            print(f"[{self.site_name}] Error fetching or parsing links from {category_url}: {e}")
        return article_infos

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        print(f"[{self.site_name}] Fetching content from {article_url}")
        try:
            async with session.get(article_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # TODO: 동아일보 기사 상세 페이지 구조에 맞는 선택자로 수정 필요
            title_tag = soup.select_one('h1.title, div.article_title h1, header.article_header h1')
            article_title = title_tag.get_text(strip=True) if title_tag else original_title
            
            article_body_tag = soup.select_one('div.article_txt, div.article_view, section.article_body')
            article_text = ""
            if article_body_tag:
                # 광고 등 불필요한 부분 제거 로직 추가 가능
                for ad_div in article_body_tag.select('div.article_ad, div.da_box, div.news_recomm'):
                    ad_div.decompose()
                paragraphs = article_body_tag.find_all('p', recursive=True)
                for p in paragraphs:
                    article_text += p.get_text(strip=True) + "\n"
            if not article_text.strip(): article_text = original_title

            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            # TODO: og:image 없을 경우 대체 로직

            return {
                'url': article_url,
                'title': article_title.strip(),
                'main_image_url': main_image_url,
                'article_text': article_text.strip(),
                'source': "donga"
            }
        except Exception as e:
            print(f"[{self.site_name}] Error fetching or parsing content from {article_url}: {e}")
        return None

    def get_news_urls_for_category(self, category_url):
        """
        카테고리 페이지에서 개별 뉴스 기사 URL을 수집합니다.
        이 메소드는 동아일보 웹사이트의 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 동아일보 카테고리 페이지 구조에 맞춰 뉴스 URL 추출 로직 구현
        news_urls = []
        print(f"[{self.name}] Extracting news URLs from {category_url} (not implemented yet)")
        return news_urls

    def extract_article_content(self, news_url):
        """
        개별 뉴스 기사 URL에서 제목, 본문, 작성일 등을 추출합니다.
        이 메소드는 동아일보 웹사이트의 기사 페이지 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 동아일보 기사 페이지 구조에 맞춰 기사 내용 추출 로직 구현
        print(f"[{self.name}] Extracting content from {news_url} (not implemented yet)")
        return None # 실제 구현 필요 