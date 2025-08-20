import requests
from newspaper import Article
from bs4 import BeautifulSoup
import time

# 네이버 검색 API 정보
client_id = "YJPNOQ0QKIigP1PTje9C"
client_secret = "Il4qo4Qusq"

# API URL
url = "https://openapi.naver.com/v1/search/news.json"

# 검색할 키워드
keyword = '비트코인'

# 요청 헤더 설정
headers = {
    "X-Naver-Client-Id": client_id,
    "X-Naver-Client-Secret": client_secret
}
# 웹 페이지 요청 시 사용할 헤더 (차단 방지)
http_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


# 요청 파라미터 설정
params = {
    "query": keyword,
    "display": 5,
    "start": 1,
    "sort": "sim"
}

try:
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()
    items = data.get('items', [])

    if not items:
        print(f"'{keyword}'에 대한 뉴스 검색 결과가 없습니다.")
    else:
        for item in items:
            naver_news_link = item.get('link')
            original_article_link = item.get('originallink')
            
            link_to_crawl = original_article_link if original_article_link else naver_news_link

            title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')

            print(f"--- [ {title} ] ---")
            print(f"  - 크롤링 대상: {link_to_crawl}")

            if not link_to_crawl:
                print("! 크롤링할 유효한 링크가 없습니다.")
                print("-" * 50)
                continue

            print("\n[기사 본문]")
            try:
                # 하이브리드 접근: 네이버 뉴스는 BeautifulSoup, 그 외는 newspaper3k
                if "n.news.naver.com" in link_to_crawl:
                    # 1. 네이버 뉴스 링크일 경우
                    page_res = requests.get(link_to_crawl, headers=http_headers)
                    page_res.raise_for_status()
                    soup = BeautifulSoup(page_res.text, 'html.parser')
                    
                    # 사용자가 제공한 HTML 구조를 기반으로, 모든 네이버 뉴스에 대해 '#newsct_article' 선택자를 사용하도록 통일
                    content = soup.select_one('#newsct_article')

                    if content:
                        # 기사 본문 내 불필요한 부분 제거 (이미지 설명, 사진 출처)
                        for el in content.select("em.img_desc, .end_photo_org"):
                            el.decompose()
                        article_text = content.get_text(separator='\n', strip=True)
                        print(article_text)
                    else:
                        print("! 네이버 뉴스에서 기사 본문 영역('#newsct_article')을 찾지 못했습니다.")
                else:
                    # 2. 그 외 언론사 원문 링크일 경우
                    article = Article(link_to_crawl, language='ko')
                    article.download()
                    article.parse()
                    if article.text and len(article.text) > 30:
                        print(article.text)
                    else:
                        print("! 기사 본문을 추출하지 못했거나 내용이 너무 짧습니다.")

            except Exception as e:
                print(f"! 기사 처리 중 오류 발생: {e}")
            
            print("-" * 50)
            time.sleep(1)

except requests.exceptions.HTTPError as errh:
    print(f"HTTP Error: {errh}")
    if 'response' in locals():
        print(f"Response: {response.text}")
except requests.exceptions.RequestException as err:
    print(f"Request Error: {err}")
except Exception as e:
    print(f"An error occurred: {e}") 