from abc import ABC, abstractmethod
import aiohttp
import asyncio

class BaseCollector(ABC):
    """
    모든 뉴스 수집기의 기반이 되는 추상 클래스입니다.
    각 뉴스 사이트의 특성에 맞게 이 클래스를 상속받아 구현합니다.
    """
    def __init__(self, site_name, base_url):
        self.site_name = site_name
        self.base_url = base_url

    @abstractmethod
    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        """
        주어진 카테고리 URL에서 기사 제목과 URL 목록을 추출합니다.
        반환값: [{'title': '기사 제목', 'url': '기사 URL'}, ...] 형태의 리스트
        """
        pass

    @abstractmethod
    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        """
        개별 기사 URL에서 상세 내용을 추출합니다.
        original_title은 링크 목록에서 가져온 초기 제목입니다.
        반환값: {'url': str, 'title': str, 'main_image_url': str | None, 'article_text': str} 형태의 딕셔너리
                  또는 실패 시 None
        """
        pass

    async def collect_by_category(self, category_name: str, category_path_segment: str) -> list[dict]:
        """
        특정 카테고리의 모든 기사를 수집합니다.
        category_path_segment는 base_url 뒤에 붙는 경로입니다 (예: 'world', 'business')
        """
        category_url = f"{self.base_url}/{category_path_segment}"
        collected_articles = []
        async with aiohttp.ClientSession() as session:
            print(f"[{self.site_name.upper()}/{category_name.upper()}] 기사 링크 수집 중... ({category_url})")
            article_infos = await self.fetch_article_links(session, category_url)

            if not article_infos:
                print(f"[{self.site_name.upper()}/{category_name.upper()}] 수집할 기사를 찾지 못했습니다.")
                return []

            print(f"[{self.site_name.upper()}/{category_name.upper()}] 총 {len(article_infos)}개의 기사 링크를 찾았습니다. 내용 수집 시작...")

            tasks = []
            for info in article_infos:
                # fetch_article_content는 이제 original_title을 인자로 받음
                tasks.append(self.fetch_article_content(session, info['url'], info['title']))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    print(f"[{self.site_name.upper()}/{category_name.upper()}] 기사 수집 중 오류: {result}")
                elif result:
                    collected_articles.append(result)
            
            print(f"[{self.site_name.upper()}/{category_name.upper()}] 총 {len(collected_articles)}개의 기사 내용 수집 완료.")
        return collected_articles
