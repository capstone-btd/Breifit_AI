from typing import List, Dict, Any, Optional
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import random
from datetime import datetime
from slugify import slugify

from .base_collector import BaseCollector
from ..utils.browser_manager import get_browser

# extract_article_details_cnn 함수는 여기에 유지
def extract_article_details_cnn(html_content, title_from_link):
    """
    CNN 기사의 HTML 콘텐츠에서 제목, 메인 이미지 URL, 본문을 추출합니다.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    article_title = None
    h1_tag = soup.find('h1', class_='headline__text')
    if h1_tag and h1_tag.get_text(strip=True):
        article_title = h1_tag.get_text(strip=True)
    else:
        article_title = title_from_link
        if not article_title:
            article_title = "제목 없음"

    main_image_url = None
    lede_container_div = soup.find('div', class_='image__lede article__lede-wrapper')
    if lede_container_div:
        dam_img_tag = lede_container_div.find('img', class_='image__dam-img', src=re.compile(r"https?://media\.cnn\.com/api/v1/images/stellar/prod/"))
        if dam_img_tag and dam_img_tag.get('src'):
            main_image_url = dam_img_tag['src']
        if not main_image_url:
            img_tag = lede_container_div.find('img', src=re.compile(r"https?://media\.cnn\.com/api/v1/images/stellar/prod/"))
            if img_tag and img_tag.get('src'):
                main_image_url = img_tag['src']
        if not main_image_url:
            picture_tag = lede_container_div.find('picture')
            if picture_tag:
                source_tag = picture_tag.find('source', srcset=re.compile(r"https?://media\.cnn\.com/api/v1/images/stellar/prod/"))
                if source_tag and source_tag.get('srcset'):
                    main_image_url = source_tag.get('srcset').split(',')[0].split(' ')[0]
    
    article_text_parts = []
    article_content_div = soup.find('div', class_='article__content')
    if article_content_div:
        for p_tag in article_content_div.find_all('p', class_=re.compile(r"paragraph")):
            article_text_parts.append(p_tag.get_text(separator=' ', strip=True))
        
        for figure_or_img_div in article_content_div.find_all('div', class_='image'):
            caption_span = figure_or_img_div.find('span', attrs={'data-editable': 'metaCaption'})
            if caption_span:
                article_text_parts.append(f"[Image Caption: {caption_span.get_text(strip=True)}]")
            credit_figcap = figure_or_img_div.find('figcaption', class_='image__credit')
            if credit_figcap:
                article_text_parts.append(f"[Image Credit: {credit_figcap.get_text(strip=True)}]")

        for ad_div in article_content_div.find_all('div', class_=re.compile(r"ad-slot|qtm-element|ad")):
            ad_div.decompose()
    else:
        print(f"경고 (CNN): <div class='article__content'>를 찾지 못했습니다. ({title_from_link})")
        # 대체 로직을 추가하거나 빈 문자열 반환 고려
        body_tag = soup.find('body')
        if body_tag:
             # 간단한 텍스트 추출, 추가 정제 필요
            for script_or_style in body_tag.find_all(['script', 'style', 'header', 'footer', 'nav', 'aside']):
                script_or_style.decompose()
            article_text_parts.append(body_tag.get_text(separator=' ', strip=True))


    body_content = "\n\n".join(article_text_parts).strip()
    return article_title, main_image_url, body_content


class CnnCollector(BaseCollector):
    def __init__(self):
        super().__init__(site_name="cnn", base_url="https://edition.cnn.com")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        print(f"[{self.site_name.upper()}] {category_url} 에서 기사 목록을 가져오는 중...")
        try:
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                if response.status != 200:
                    print(f"[{self.site_name.upper()}] 메인 페이지 로딩 오류: {response.status}, URL: {category_url}")
                    return []
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] 메인 페이지 로딩 시간 초과: {category_url}")
            return []
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] 메인 페이지 로딩 중 ClientError 발생: {e}, URL: {category_url}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        articles = []
        # CNN 월드 페이지의 링크 선택자 (이전 코드 기반)
        for link_tag in soup.select('a.container__link.container__link--type-article'):
            href = link_tag.get('href')
            if href:
                article_url = urljoin(self.base_url, href) # urljoin 사용으로 상대/절대 경로 모두 처리

                headline_span = link_tag.find('span', class_='container__headline-text')
                title = headline_span.text.strip() if headline_span else "제목 없음"
                
                # 중복 URL 체크
                if not any(existing_article['url'] == article_url for existing_article in articles):
                    articles.append({'title': title, 'url': article_url})
        
        print(f"[{self.site_name.upper()}] 총 {len(articles)}개의 고유한 기사 링크를 찾았습니다 ({category_url}).")
        return articles

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        await asyncio.sleep(random.uniform(1, 3))
        print(f"[{self.site_name.upper()}/{category.upper()}] 기사 내용 가져오기 시작: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    print(f"[{self.site_name.upper()}/{category.upper()}] 기사 페이지 로딩 오류: {response.status}, URL: {article_url}")
                    return None
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

        try:
            # CNN용 상세 추출 함수 사용
            extracted_title, image_url, article_text = extract_article_details_cnn(html_content, original_title)
        except Exception as e:
            print(f"[{self.site_name.upper()}/{category.upper()}] HTML 파싱 또는 내용 추출 중 오류 ({article_url}): {e}")
            return None

        if not article_text: # 본문 내용이 없으면 유효하지 않은 기사로 판단
            print(f"[{self.site_name.upper()}/{category.upper()}] 기사 본문 내용을 추출하지 못했습니다: {article_url}")
            return None

        return {
            "url": article_url,
            "title": extracted_title,
            "main_image_url": image_url,
            "article_text": article_text,
            "source": self.site_name,
            "category": category
        }

    def get_file_name(self, article_title: str) -> str:
        if article_title:
            # 파일명으로 사용하기 위해 제목을 slugify 처리
            slug_title = slugify(article_title)
            if not slug_title:
                slug_title = f"article-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            return f"{slug_title}.json"
        return f"article-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.json"

# 기존 cnn.py의 main() 함수와 파일 저장 로직은
# run_collection.py 또는 main.py에서 처리하도록 분리됩니다.
# 이 파일은 CnnCollector 클래스 정의에 집중합니다. 