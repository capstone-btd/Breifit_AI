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

class HankyorehCollector(BaseCollector):
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            site_config = config_data['sites']['hankyoreh']
            base_url = site_config['base_url']
        except Exception as e:
            print(f"[HankyorehCollector] 설정 파일 로드 오류 ({config_path}): {e}. 기본 base_url을 사용합니다.")
            base_url = "https://www.hani.co.kr"
        super().__init__(site_name="hankyoreh", base_url=base_url)
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
            
            article_list_container = soup.select_one('div.section_left__5BOCT ul')
            if not article_list_container:
                print(f"[{self.site_name}] Could not find article list container on {category_url}")
                return article_infos

            articles = article_list_container.select('li.ArticleList_item___OGQO article')
            
            for article_tag in articles:
                link_tag = article_tag.select_one('a.BaseArticleCard_link__Q3YFK')
                title_tag = article_tag.select_one('div.BaseArticleCard_title__TVFqt')

                if link_tag and title_tag:
                    href = link_tag.get('href')
                    title = title_tag.get_text(strip=True)
                    
                    if href and title:
                        # 상대 경로일 경우 base_url과 조합
                        if href.startswith('/'):
                            href = self.base_url + href
                        
                        if href.startswith(self.base_url): # 전체 URL이 base_url로 시작하는지 다시 확인
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
            
            # TODO: 한겨레 기사 상세 페이지 구조에 맞는 선택자로 수정 필요
            title_tag = soup.select_one('span.title, h1.title, header h1')
            article_title = title_tag.get_text(strip=True) if title_tag else original_title
            
            article_body_tag = soup.select_one('div.article-text, div.text, section.article-text-font-size')
            article_text_content = ""
            if article_body_tag:
                # 기자 정보, 광고 등 제외
                for el in article_body_tag.select('.journalist-info, .advertise, .related-articles, .copyright'):
                    el.decompose()
                paragraphs = article_body_tag.find_all('p', recursive=True)
                for p in paragraphs:
                    article_text_content += p.get_text(strip=True) + "\n"
            if not article_text_content.strip(): article_text_content = original_title

            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            # TODO: og:image 없을 경우 대체 로직

            if not article_text_content.strip():
                print(f"[{self.site_name.upper()}/{category.upper()}] 기사 본문 내용을 추출하지 못했습니다: {article_url}")
                return None

            return {
                "url": article_url,
                "title": article_title,
                "main_image_url": main_image_url,
                "article_text": article_text_content.strip(),
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
        이 메소드는 한겨레 웹사이트의 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 한겨레 카테고리 페이지 구조에 맞춰 뉴스 URL 추출 로직 구현
        news_urls = []
        print(f"[{self.name}] Extracting news URLs from {category_url} (not implemented yet)")
        return news_urls

    def extract_article_content(self, news_url):
        """
        개별 뉴스 기사 URL에서 제목, 본문, 작성일 등을 추출합니다.
        이 메소드는 한겨레 웹사이트의 기사 페이지 HTML 구조에 맞게 구현해야 합니다.
        """
        # TODO: 한겨레 기사 페이지 구조에 맞춰 기사 내용 추출 로직 구현
        print(f"[{self.name}] Extracting content from {news_url} (not implemented yet)")
        return None # 실제 구현 필요

    async def search_by_keyword(self, keyword: str) -> list[dict]:
        """
        키워드로 한겨레 기사를 검색합니다.
        """
        search_url = f"https://search.hani.co.kr/search?searchword={keyword}"
        
        async with aiohttp.ClientSession() as session:
            try:
                print(f"[{self.site_name}] 키워드 '{keyword}' 검색: {search_url}")
                async with session.get(search_url, headers=self.headers, timeout=30) as response:
                    response.raise_for_status()
                    html_content = await response.text()
                
                soup = BeautifulSoup(html_content, 'html.parser')
                articles = []
                
                # 한겨레 검색 결과에서 기사 링크 추출
                search_results = soup.select('div.search-result-item, div.ArticleList_item___OGQO')
                
                for item in search_results[:10]:  # 최대 10개 기사만 수집
                    try:
                        link_tag = item.select_one('a, h3 a')
                        if link_tag:
                            article_url = link_tag.get('href')
                            title = link_tag.get_text(strip=True)
                            
                            if article_url and title:
                                if not article_url.startswith('http'):
                                    article_url = f"https://www.hani.co.kr{article_url}"
                                
                                # 개별 기사 내용 수집
                                article_data = await self.fetch_article_content(session, article_url, title, 'search')
                                if article_data:
                                    articles.append(article_data)
                                
                    except Exception as e:
                        print(f"[{self.site_name}] 검색 결과 처리 중 오류: {e}")
                        continue
                
                print(f"[{self.site_name}] 키워드 '{keyword}'로 {len(articles)}개 기사 수집 완료")
                return articles
                
            except Exception as e:
                print(f"[{self.site_name}] 키워드 '{keyword}' 검색 중 오류: {e}")
                return [] 