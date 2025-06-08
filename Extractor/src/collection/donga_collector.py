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

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        await asyncio.sleep(random.uniform(1, 3)) # 1~3초 랜덤 지연
        print(f"[{self.site_name.upper()}/{category.upper()}] 기사 내용 가져오기 시작: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=self.timeout_seconds) as response:
                response.raise_for_status()
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            title_tag = soup.select_one('h1.title, div.article_title h1, header.view_head h1, header.article_header h1')
            article_title = title_tag.get_text(strip=True) if title_tag else original_title
            
            # 기사 본문 영역 선택자 변경
            article_body_tag = soup.select_one('section.news_view')
            
            article_text = ""
            if article_body_tag:
                # 광고, 이미지 캡션, 관련기사 등 불필요한 부분 제거
                elements_to_remove = []
                # 클래스에 'ad', '광고', 'AD' (대소문자 구분 없이) 포함하는 div 제거
                elements_to_remove.extend(article_body_tag.find_all('div', class_=lambda x: x and any(s.lower() in x.lower() for s in ['ad', '광고', 'AD'])))
                # figure 태그 (이미지 및 캡션 포함 가능성) 제거
                elements_to_remove.extend(article_body_tag.find_all('figure'))
                # script, style 태그 제거
                elements_to_remove.extend(article_body_tag.find_all(['script', 'style']))
                # 기자 정보, 댓글, 공유 버튼 등 영역 제거 (더 구체적인 선택자 필요시 추가)
                elements_to_remove.extend(article_body_tag.select('div.reporter_info, div.arcticle_relation, section.reporter_sec, div.view_head_setting, div.article_dk_view, div.article_issue'))
                # 추가적으로 제거할 영역 (제공된 HTML 기반)
                elements_to_remove.extend(article_body_tag.select('div.view_m_adK, div.view_ad06, div.view_m_adA, div.article_end, section#poll_content, div.subscribe_wrap, div#is_relation_m, div.view_m_adI, div#is_trend_m, div.view_ad07, div.view_m_adD, div#is_relation_tablet, div#is_trend_tablet'))

                for element in elements_to_remove:
                    element.decompose()
                
                # 텍스트 추출 (줄바꿈 유지, 앞뒤 공백 제거)
                article_text = article_body_tag.get_text(separator='\\n', strip=True)

                # 특정 패턴 필터링 (기자 정보 등) - 필요시 정규식 사용
                lines = article_text.split('\\n')
                filtered_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped: # 빈 줄 제거
                        continue
                    # 흔히 발견되는 기자 정보 패턴 (더 정교하게 수정 가능)
                    if "@donga.com" in line_stripped or "기자" in line_stripped and len(line_stripped) < 30: # 짧은 줄의 기자 언급
                        # 좀 더 정교한 필터링 로직 (예: 문장 시작이 아니거나 특정 단어와 함께 나올 때)
                        if not (line_stripped.startswith("동아닷컴") or line_stripped.startswith("입력 ") or line_stripped.startswith("수정 ")):
                             # 기사 내용일 가능성이 있는 '기자' 언급은 유지 (예: "기자회견")
                            if not any(keyword in line_stripped for keyword in ["기자회견", "기자간담회"]):
                                print(f"[{self.site_name.upper()}/{category.upper()}] 필터링된 라인: {line_stripped}")
                                continue
                    if "▶" in line_stripped or "ⓒ" in line_stripped: # 채널 추가, 저작권 등
                         print(f"[{self.site_name.upper()}/{category.upper()}] 필터링된 라인 (특수문자): {line_stripped}")
                         continue
                    filtered_lines.append(line_stripped)
                article_text = "\\n".join(filtered_lines)

            if not article_text.strip():
                 print(f"[{self.site_name.upper()}/{category.upper()}] 기사 본문 내용을 찾지 못했습니다. URL: {article_url}")

            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            # TODO: og:image 없을 경우 대체 로직

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