from abc import ABC, abstractmethod
import aiohttp
import asyncio

class BaseCollector(ABC):
    """
    기능: 모든 뉴스 수집기의 기반이 되는 추상 기본 클래스이다.
    input: 없음
    output: 없음
    """
    def __init__(self, site_name, base_url):
        self.site_name = site_name
        self.base_url = base_url
        self.timeout_seconds = 30 # 기본 타임아웃 30초로 설정

    @abstractmethod
    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        """
        기능: 주어진 카테고리 URL에서 기사 제목과 URL 목록을 추출한다.
        input: aiohttp 클라이언트 세션(session), 카테고리 URL(category_url)
        output: {'title': str, 'url': str} 딕셔너리의 리스트 (list[dict])
        """
        pass

    @abstractmethod
    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str, category: str) -> dict | None:
        """
        기능: 개별 기사 URL에서 상세 내용을 추출한다.
        input: aiohttp 클라이언트 세션(session), 기사 URL(article_url), 원본 제목(original_title), 카테고리(category)
        output: 기사 상세 정보 딕셔너리 또는 실패 시 None (dict | None)
        """
        pass

    async def collect_by_category(self, category_name: str, category_path_segment: str) -> list[dict]:
        """
        기능: 특정 카테고리의 모든 기사를 수집한다.
        input: 카테고리 이름(category_name), 카테고리 경로 세그먼트(category_path_segment)
        output: 수집된 기사 데이터 딕셔너리의 리스트 (list[dict])
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
                # fetch_article_content는 이제 original_title과 category를 인자로 받음
                tasks.append(self.fetch_article_content(session, info['url'], info['title'], category_name))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    print(f"[{self.site_name.upper()}/{category_name.upper()}] 기사 수집 중 오류: {result}")
                elif result:
                    collected_articles.append(result)
            
            print(f"[{self.site_name.upper()}/{category_name.upper()}] 총 {len(collected_articles)}개의 기사 내용 수집 완료.")
        return collected_articles
