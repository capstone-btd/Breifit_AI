import asyncio
import aiohttp
# from urllib.parse import quote # params 인자가 처리하므로 보통 직접 필요 없음
from .base_collector import BaseCollector
# from datetime import datetime # Archive API 용이므로 제거

class NYTCollector(BaseCollector):
    def __init__(self):
        # Top Stories API를 기본 base_url로 사용
        super().__init__(site_name="New York Times", base_url="https://api.nytimes.com/svc/topstories/v2")
        self.article_search_base_url = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
        # 사용자님께서 제공해주신 API 키를 사용합니다.
        self.api_key = "yTpILYlN7Hxxsimo55CPhe4Da6NJG8oA" 

        if not self.api_key or self.api_key == "yTpILYlN7Hxxsimo55CPhe4Da6NJG8oA": # 원본 플레이스홀더와도 비교
            print("경고: NYTCollector에 유효한 API 키가 설정되지 않았습니다.")
            # 실제 운영 시에는 키가 없으면 에러를 발생시키거나, 프로그램을 중단하는 것이 좋습니다.
            # raise ValueError("NYT API 키가 설정되지 않았습니다.")

    async def fetch_article_links(self, session: aiohttp.ClientSession, section_name: str) -> list[dict]:
        """
        NYT Top Stories API를 사용하여 주어진 섹션의 기사 제목과 URL 목록을 추출합니다.
        section_name은 API가 요구하는 섹션명입니다 (예: 'world', 'business').
        이 값은 news_sites.yaml 파일의 category 값에서 옵니다.
        """
        if not self.api_key or self.api_key == "yTpILYlN7Hxxsimo55CPhe4Da6NJG8oA":
            print(f"[{self.site_name.upper()}/{section_name.upper()}] API 키가 유효하지 않아 기사 링크를 수집할 수 없습니다.")
            return []

        # Top Stories API URL: {base_url}/{section_name}.json
        api_url = f"{self.base_url}/{section_name}.json"
        params = {'api-key': self.api_key}
        
        print(f"Fetching links from NYT Top Stories API for section: {section_name}")
        article_links = []
        try:
            async with session.get(api_url, params=params) as response:
                response.raise_for_status()  # 200 OK가 아니면 에러 발생
                data = await response.json()
                
                results = data.get("results", [])
                for article_data in results:
                    title = article_data.get("title")
                    web_url = article_data.get("url") 
                    
                    if title and web_url:
                        article_links.append({"title": title, "url": web_url})
            
            print(f"Found {len(article_links)} links from NYT Top Stories API for section '{section_name}'")
            return article_links
        except aiohttp.ClientResponseError as e:
            print(f"Error fetching links from NYT Top Stories API ({section_name}): {e.status} {e.message}")
            if e.status == 401 or e.status == 403:
                print("API 키가 유효하지 않거나 요청 권한이 없는 것 같습니다. API 키와 구독 상태를 확인해주세요.")
            elif e.status == 404:
                 print(f"Top Stories API에서 '{section_name}' 섹션을 찾을 수 없습니다. 유효한 섹션명인지 확인해주세요.")
            elif e.status == 429:
                print("API 요청 빈도가 너무 높습니다. 잠시 후 다시 시도해주세요.")
        except Exception as e:
            print(f"An unexpected error occurred while fetching links from NYT Top Stories API ({section_name}): {e}")
        return []

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        """
        NYT Article Search API를 사용하여 개별 기사 URL에서 상세 내용을 추출합니다.
        article_url은 Top Stories API에서 얻은 기사의 웹사이트 URL입니다.
        """
        if not self.api_key or self.api_key == "yTpILYlN7Hxxsimo55CPhe4Da6NJG8oA":
            print(f"[{self.site_name.upper()}] API 키가 유효하지 않아 기사 내용을 수집할 수 없습니다: {article_url}")
            return None

        params = {
            'fq': f'web_url:("{article_url}")', 
            'api-key': self.api_key
        }
        
        print(f"Fetching content from NYT Article Search API for: {article_url}")
        try:
            async with session.get(self.article_search_base_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                docs = data.get("response", {}).get("docs", [])
                if not docs:
                    print(f"No article found in Article Search API for URL: {article_url}")
                    return None 
                
                doc = docs[0] 
                
                title = doc.get("headline", {}).get("main", original_title)
                article_text = doc.get("abstract")
                if not article_text:
                    article_text = doc.get("lead_paragraph", "")
                
                main_image_url = None
                multimedia = doc.get("multimedia", [])
                if multimedia:
                    for media_item in multimedia:
                        if media_item.get("type") == "image" and media_item.get("url"):
                            img_path = media_item.get("url")
                            if not img_path.startswith("http"):
                                main_image_url = f"https://static01.nyt.com/{img_path}"
                            else:
                                main_image_url = img_path
                            break 
                
                if title and article_text: 
                    print(f"Successfully fetched content via Article Search API for: {title}")
                    return {
                        'url': article_url, 
                        'title': title,
                        'main_image_url': main_image_url,
                        'article_text': article_text, 
                        'published_date': doc.get('pub_date'), 
                        'source': doc.get('source'),           
                        'document_type': doc.get('document_type'), 
                    }
                else:
                    print(f"Could not extract sufficient content via Article Search API from {article_url}. Title: {title}, Text found: {bool(article_text)}")
                    return None

        except aiohttp.ClientResponseError as e:
            print(f"Error fetching content from NYT Article Search API ({article_url}): {e.status} {e.message}")
        except Exception as e:
            print(f"An unexpected error occurred while fetching content from NYT Article Search API ({article_url}): {e}")
        return None

if __name__ == '__main__':
    async def test_nyt_top_stories_and_search_collection():
        collector = NYTCollector()
        if not collector.api_key or collector.api_key == "yTpILYlN7Hxxsimo55CPhe4Da6NJG8oA":
             print("테스트를 위해 NYTCollector의 self.api_key를 실제 값으로 설정해주세요.")
             return

        test_category_display_name = "NYT Technology" 
        test_api_section_name = "technology" 
        
        print(f"--- Testing NYT Top Stories & Article Search for: {test_category_display_name} (API section: {test_api_section_name}) ---")
        
        all_collected_articles = []
        async with aiohttp.ClientSession() as session:
            article_infos = await collector.fetch_article_links(session, test_api_section_name)

            if not article_infos:
                print(f"수집할 기사 링크를 찾지 못했습니다 ({test_api_section_name}).")
            else:
                print(f"총 {len(article_infos)}개의 기사 링크를 찾았습니다 ({test_api_section_name}). 내용 수집 시작...")
                tasks = []
                for info in article_infos[:3]: 
                    tasks.append(collector.fetch_article_content(session, info['url'], info['title']))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        print(f"기사 내용 수집 중 오류 발생: {result}")
                    elif result:
                        all_collected_articles.append(result)
        
        if all_collected_articles:
            print(f"\nCollected {len(all_collected_articles)} full articles from '{test_category_display_name}'. First few:")
            for i, article in enumerate(all_collected_articles): 
                print(f"  Article {i+1}:")
                print(f"    Title: {article['title']}")
                print(f"    URL: {article['url']}")
                print(f"    Image: {article.get('main_image_url', 'N/A')}")
                print(f"    Published Date: {article.get('published_date', 'N/A')}")
                print(f"    Abstract: {article.get('article_text', '')[:100]}...")
                print("-" * 20)
        else:
            print(f"No full articles collected for section '{test_category_display_name}'.")

    # asyncio.run(test_nyt_top_stories_and_search_collection())
    
    print("\nNYTCollector가 Top Stories API와 Article Search API를 사용하도록 수정되었습니다.")
    print("configs/news_sites.yaml의 NYT 카테고리 값들을 Top Stories API 섹션명으로 수정한 후,")
    print("`python scripts/run_collection.py`를 통해 실행해보세요.") 