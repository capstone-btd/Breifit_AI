# 일단 이 코드는 사용하지 않습니다. 그냥 개망한 코드. 403 forbidden때문에
import aiohttp
from bs4 import BeautifulSoup
from ..base_collector import BaseCollector
import asyncio

class APCollector(BaseCollector):
    def __init__(self):
        # 기본 URL을 https://apnews.com 으로 변경하고, site_name도 AP News로 일반화합니다.
        super().__init__(site_name="AP News", base_url="https://apnews.com")

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        """
        AP News의 특정 카테고리 URL에서 기사 제목과 URL 목록을 추출합니다.
        """
        article_links = []
        try:
            print(f"[{self.site_name.upper()}] 다음 URL에서 링크 수집 시도: {category_url}")
            # 사용자 에이전트 추가 시도
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with session.get(category_url, timeout=15, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # AP News 기사 링크 구조 (반드시 실제 웹사이트 확인 후 수정 필요!)
            # 시도 1: 일반적인 카드 형태
            cards = soup.find_all('div', class_=['Card', 'FeedCard', 'PageList-items-item'])
            
            processed_urls = set() # 중복 URL 처리

            for card in cards:
                link_tag = card.find('a', href=True)
                if not link_tag:
                    continue

                href = link_tag.get('href')
                if not href or href in processed_urls:
                    continue

                # AP News는 대부분 절대 경로 또는 루트 상대 경로를 사용
                if href.startswith('/'):
                    full_url = self.base_url + href 
                elif href.startswith(self.base_url):
                    full_url = href
                else: # 완전한 URL이 아닌 경우 건너뛰거나, 사이트 구조에 맞게 조합
                    # print(f"[DEBUG] 유효하지 않거나 처리할 수 없는 href: {href}")
                    continue 
                
                title_text = ""
                # 제목 태그 우선 순위: h1-h6, div.PagePromo-title, a 태그 자체 텍스트
                title_tag = link_tag.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], class_=lambda x: x != 'Timestamp' if x else True)
                if title_tag:
                    title_text = title_tag.text.strip()
                
                if not title_text:
                    title_promo_tag = card.find('div', class_='PagePromo-title') # AP News에서 자주 보임
                    if title_promo_tag:
                        title_text = title_promo_tag.text.strip()
                
                if not title_text: # 마지막 시도로 a 태그 자체의 텍스트 중 긴 것을 사용
                    a_text = link_tag.text.strip()
                    if len(a_text) > 20 : # 너무 짧은 텍스트는 제목이 아닐 가능성이 높음
                        title_text = a_text

                if title_text and full_url:
                    article_links.append({'title': title_text, 'url': full_url})
                    processed_urls.add(href)
            
            # 시도 2: data-key 속성을 가진 링크 (위에서 못 찾았을 경우)
            if not article_links:
                # print("[DEBUG] Card/FeedCard/PageList-items-item 에서 링크 못찾음. data-key 시도...")
                links_with_datakey = soup.find_all('a', attrs={'data-key': 'card-headline-link'}, href=True)
                for link_tag in links_with_datakey:
                    href = link_tag.get('href')
                    if not href or href in processed_urls:
                        continue
                    
                    full_url = ""
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    elif href.startswith(self.base_url):
                        full_url = href
                    else:
                        continue
                    
                    title_text = link_tag.text.strip()
                    if title_text and full_url:
                        article_links.append({'title': title_text, 'url': full_url})
                        processed_urls.add(href)

            # 중복 제거 (URL 기준 최종)
            final_links = []
            final_urls = set()
            for link_info in article_links:
                if link_info['url'] not in final_urls:
                    final_links.append(link_info)
                    final_urls.add(link_info['url'])
            article_links = final_links

        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] 링크 수집 중 HTTP 오류 (URL: {category_url}): {e}")
        except Exception as e:
            print(f"[{self.site_name.upper()}] 링크 수집 중 알 수 없는 오류 (URL: {category_url}): {e}")
            
        if not article_links:
            print(f"[{self.site_name.upper()}] {category_url} 에서 기사 링크를 최종적으로 찾지 못했습니다. HTML 구조 확인 및 선택자 수정이 필요합니다.")
        return article_links

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        """
        개별 기사 URL에서 상세 내용을 추출합니다.
        """
        try:
            print(f"[{self.site_name.upper()}] 다음 URL에서 내용 수집 시도: {article_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with session.get(article_url, timeout=15, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')
            
            title = original_title # 기본값으로 원래 제목 사용
            title_tag = soup.find('h1', class_=['Page-headline', 'Article-headline', 'HeadLine'])
            if not title_tag:
                title_tag = soup.find('h1')
            if title_tag:
                title = title_tag.text.strip()

            article_body_tag = soup.find('div', class_=['Article', 'RichTextStoryBody', 'article-content'])
            if not article_body_tag: 
                 article_body_tag = soup.find('article')

            article_text_parts = []
            if article_body_tag:
                paragraphs = article_body_tag.find_all('p', recursive=True) # 모든 하위 p 태그 검색
                for p in paragraphs:
                    # 광고나 관련기사 링크 등 불필요한 문단 제거 (예시, 실제 클래스명 확인 필요)
                    if p.parent.name == 'aside' or (p.get('class') and ('ad-' in " ".join(p.get('class')) or 'related-' in " ".join(p.get('class')))):
                        continue
                    article_text_parts.append(p.text.strip())
            
            article_text = "\n\n".join(filter(None, article_text_parts)) 
            if not article_text and article_body_tag: # p태그로 못찾았지만 본문태그는 있을경우, 전체 text 시도
                article_text = article_body_tag.get_text(separator="\n\n", strip=True)
            
            if not article_text:
                print(f"[{self.site_name.upper()}] 본문 내용을 찾을 수 없습니다: {article_url}. HTML 구조 확인 필요.")
                return None

            main_image_url = None
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                main_image_url = og_image_tag['content']
            else:
                picture_tag = soup.find('picture')
                if picture_tag:
                    source_tag = picture_tag.find('source', srcset=True)
                    if source_tag:
                        main_image_url = source_tag['srcset'].split(',')[0].strip().split(' ')[0]
                    else:
                        img_tag_in_picture = picture_tag.find('img', src=True)
                        if img_tag_in_picture:
                             main_image_url = img_tag_in_picture['src']
                if not main_image_url:
                    figure_tag = soup.find('figure')
                    if figure_tag:
                        img_tag = figure_tag.find('img', src=True)
                        if img_tag:
                            main_image_url = img_tag['src']
            
            return {
                'url': article_url,
                'title': title,
                'main_image_url': main_image_url,
                'article_text': article_text
            }

        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] 기사 내용 수집 중 HTTP 오류 (URL: {article_url}): {e}")
        except Exception as e:
            print(f"[{self.site_name.upper()}] 기사 내용 수집 중 알 수 없는 오류 (URL: {article_url}): {e}")
        return None

if __name__ == '__main__':
    # import asyncio # 이미 위에서 임포트 함

    async def test_category(collector: APCollector, category_name: str, category_path: str):
        print(f"\n--- {collector.site_name} {category_name} 기사 수집 테스트 ---")
        collected_articles = await collector.collect_by_category(category_name=category_name, category_path_segment=category_path)
        
        if collected_articles:
            print(f"[{collector.site_name.upper()}/{category_name.upper()}] 테스트로 수집된 기사 ({len(collected_articles)}개 중 최대 2개):")
            for i, article in enumerate(collected_articles[:2]): 
                print(f"  {i+1}. 제목: {article['title']}")
                print(f"     URL: {article['url']}")
                print(f"     이미지: {article['main_image_url']}")
                article_text_snippet = article['article_text'][:200].replace('\n', ' ') # 미리보기 길이 증가
                print(f"     본문 일부: {article_text_snippet}...")
        else:
            print(f"[{collector.site_name.upper()}/{category_name.upper()}] 해당 카테고리에서 기사를 수집하지 못했습니다. HTML 구조를 직접 확인하고 코드를 수정해야 합니다.")

    async def main():
        collector = APCollector()

        # AP News 카테고리 경로 (실제 AP News 웹사이트 확인 필요)
        # 우선 Politics와 Sports 두 카테고리만 테스트하고, 요청 사이에 5초의 대기 시간을 둡니다.
        categories_to_test = {
            "Politics": "politics",
            "Sports": "sports", 
            # "Entertainment": "entertainment", 
            # "Business": "business",
            # "Science": "science", 
            # "Technology": "technology", 
            # "Health": "health",
            # "Lifestyle": "lifestyle",
            # "World News": "world-news"
        }
        
        first_category = True
        for name, path in categories_to_test.items():
            if not first_category:
                print(f"\n다음 카테고리 테스트 전 5초 대기...")
                await asyncio.sleep(5) # 연속 요청 방지를 위해 5초 대기
            await test_category(collector, name, path)
            first_category = False

    asyncio.run(main()) 