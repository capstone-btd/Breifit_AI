import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

from .base_collector import BaseCollector

class NprCollector(BaseCollector):
    def __init__(self):
        super().__init__(site_name="npr", base_url="https://www.npr.org")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

    async def fetch_article_links(self, session: aiohttp.ClientSession, category_url: str) -> list[dict]:
        await asyncio.sleep(1)
        print(f"[{self.site_name.upper()}] Fetching article links from: {category_url}")
        article_links = []
        try:
            async with session.get(category_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] Timeout error fetching page: {category_url}")
            return []
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] ClientError fetching page: {e}, URL: {category_url}")
            return []
        except Exception as e:
            print(f"[{self.site_name.upper()}] Unknown error fetching HTML ({category_url}): {e}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        links_found = set()

        list_items = soup.find_all('article', class_=re.compile(r'(item|story-wrap|hp-item|recommended-item)'))
        if not list_items:
             list_items.extend(soup.find_all('div', class_=re.compile(r'(item|story-wrap|hp-item|recommended-item)')))

        # 정규식에서 작은따옴표 문제를 해결하기 위해 raw string과 이중 작은따옴표를 사용합니다.
        path_regex_exclude = (
            r"/(series|people|program|podcast|tag|live-updates|event|station|music|about-npr)/|"
            r"^(/(stations|newsletter|corrections|contact|help|press|ethics|careers|support|shop))|"
            r"(^(/(national|world|politics|business|health|science|climate|race|culture|books|movies|television|pop-culture|food|art-design|performing-arts|life-kit|gaming|all-songs-considered|tiny-desk|new-music-friday|music-features|live-sessions|morning-edition|weekend-edition-saturday|weekend-edition-sunday|all-things-considered|fresh-air|up-first|embedded|the-npr-politics-podcast|throughline|trumps-terms|trump''s-terms)/?$))"
        )
        path_regex_include = r'/\d{4}/\d{2}/\d{2}/\d+/'

        for item in list_items:
            link_tag = item.find('a', href=True)
            title_tag = item.find(['h2', 'h3'], class_='title')
            if not title_tag:
                 title_tag = item.find(['h2', 'h3'])

            if link_tag and title_tag:
                href = link_tag.get('href')
                title_text = title_tag.text.strip()

                if href and title_text and len(title_text) > 5 and href not in links_found:
                    full_url = urljoin(self.base_url, href)
                    parsed_url = urlparse(full_url)
                    
                    if parsed_url.netloc == 'www.npr.org' and \
                       not re.search(path_regex_exclude, parsed_url.path, re.I) and \
                       re.search(path_regex_include, parsed_url.path):

                        normalized_category_url = category_url.rstrip('/')
                        normalized_full_url = full_url.rstrip('/')
                        if normalized_full_url == normalized_category_url:
                            continue
                        
                        article_links.append({'title': title_text, 'url': full_url})
                        links_found.add(href)
                        links_found.add(full_url)
            
        if not article_links:
            title_tags = soup.find_all(['h2', 'h3', 'h4'], class_='title')
            for tt in title_tags:
                link_tag = tt.find_parent('a', href=True)
                if link_tag:
                    href = link_tag.get('href')
                    title_text = tt.text.strip()
                    if href and title_text and len(title_text) > 5 and href not in links_found:
                        full_url = urljoin(self.base_url, href)
                        parsed_url = urlparse(full_url)

                        if parsed_url.netloc == 'www.npr.org' and \
                           not re.search(path_regex_exclude, parsed_url.path, re.I) and \
                           re.search(path_regex_include, parsed_url.path):

                            normalized_category_url = category_url.rstrip('/')
                            normalized_full_url = full_url.rstrip('/')
                            if normalized_full_url == normalized_category_url:
                                continue

                            article_links.append({'title': title_text, 'url': full_url})
                            links_found.add(href)
                            links_found.add(full_url)

        final_links = []
        seen_urls = set()
        for link_info in article_links:
            if link_info['url'] not in seen_urls:
                final_links.append(link_info)
                seen_urls.add(link_info['url'])
        article_links = final_links

        if not article_links:
            print(f"[{self.site_name.upper()}] No article links found on {category_url}. Check selectors or page structure.")
        else:
            print(f"[{self.site_name.upper()}] Found {len(article_links)} unique article links on {category_url}.")
        return article_links

    async def fetch_article_content(self, session: aiohttp.ClientSession, article_url: str, original_title: str) -> dict | None:
        await asyncio.sleep(1)
        print(f"[{self.site_name.upper()}] Fetching content for: {original_title} ({article_url})")
        try:
            async with session.get(article_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
        except asyncio.TimeoutError:
            print(f"[{self.site_name.upper()}] Timeout error fetching article: {article_url}")
            return None
        except aiohttp.ClientError as e:
            print(f"[{self.site_name.upper()}] ClientError fetching article: {e}, URL: {article_url}")
            return None
        except Exception as e:
            print(f"[{self.site_name.upper()}] Unknown error fetching article HTML ({article_url}): {e}")
            return None

        soup = BeautifulSoup(html_content, 'html.parser')
        article_title = original_title
        main_image_url = None
        article_text_parts = []

        og_title_tag = soup.find('meta', property='og:title')
        if og_title_tag and og_title_tag.get('content'):
            article_title = og_title_tag['content']
        else:
            title_h1 = soup.find('h1', class_=re.compile(r'(title|storytitle)', re.I))
            if not title_h1:
                title_h1 = soup.find('div', class_=re.compile(r'(storytitle|headline)', re.I))
                if title_h1:
                    actual_h1 = title_h1.find('h1')
                    article_title = actual_h1.text.strip() if actual_h1 else title_h1.text.strip()
                else:
                    title_h1 = soup.find('h1')
                    if title_h1:
                        article_title = title_h1.text.strip()
            elif title_h1:
                article_title = title_h1.text.strip()

        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.get('content'):
            main_image_url = og_image_tag['content']
        else:
            image_wrapper = soup.find('div', class_=re.compile(r'(imagewrap|fullpage|lede|primary-image)', re.I))
            if image_wrapper:
                img_tag = image_wrapper.find('img', src=True)
                if img_tag:
                    main_image_url = urljoin(article_url, img_tag.get('src'))
            if not main_image_url:
                figure_tag = soup.find('figure', class_=re.compile(r'(image|photo|media)', re.I))
                if not figure_tag:
                    figure_tag = soup.find('figure')
                if figure_tag:
                    img_tag = figure_tag.find('img', src=True)
                    if img_tag:
                        main_image_url = urljoin(article_url, img_tag.get('src'))

        story_text_div = soup.find('div', id='storytext')
        if not story_text_div:
            story_text_div = soup.find('div', class_=re.compile(r'(storytext|storyContent|article-body|text-content|content_body|content|text)', re.I))
        if not story_text_div:
            story_text_div = soup.find('article')
        if not story_text_div:
            story_text_div = soup.find(['main', 'div'], attrs={'role': 'main'})
            if not story_text_div:
                story_text_div = soup.find('main')

        if story_text_div:
            paragraphs = story_text_div.find_all('p', recursive=True)
            for p in paragraphs:
                text = p.text.strip()
                
                parent_exclusion_classes = r'(caption|credit|byline|dateline|sidebar|related-links|pullquote|transcript|player|ad|share-tools|timestamp|program-block)'
                child_exclusion_classes = r'(audio-|podcast-|player-trigger|soundcite)'
                text_exclusion_patterns = r"^(Sponsor Message|Transcript|Listen\s·|Subscribe to|Download|Embed|Hide caption|Toggle caption|Correction:|Editor''s note:)|\(SOUNDBITE OF|All rights reserved)|Follow us on Twitter|Sign up for our newsletter"
                
                if text and len(text) > 25 and \
                   not p.find_parent(class_=re.compile(parent_exclusion_classes, re.I)) and \
                   not p.find(class_=re.compile(child_exclusion_classes, re.I)) and \
                   not re.search(text_exclusion_patterns, text, re.I) and \
                   not (p.find('strong') and p.find('strong').text.strip().lower() == 'transcript') and \
                   ' NPR.' not in text :
                    article_text_parts.append(text)
        else:
            print(f"[{self.site_name.upper()}] Article body container not found for {article_url}. Check selectors.")
            return None

        if not article_text_parts:
            print(f"[{self.site_name.upper()}] No text found in article: {article_url}")
            return None

        full_article_text = '\n\n'.join(article_text_parts)

        return {
            'url': article_url,
            'title': str(article_title).strip() if article_title else original_title.strip(),
            'main_image_url': str(main_image_url).strip() if main_image_url else None,
            'article_text': full_article_text.strip()
        }

# Test code (uncomment to run)
# async def main_test():
#     collector = NprCollector()
#     test_category_path = "sections/health" 
#     collected_articles = await collector.collect_by_category("Health Section", test_category_path)
    
#     if collected_articles:
#         print(f"\nSuccessfully collected {len(collected_articles)} articles from NPR - {test_category_path}.")
#         # for i, article in enumerate(collected_articles):
#         #     print(f"\n--- Article {i+1} ---")
#         #     print(f"Title: {article['title']}")
#         #     print(f"URL: {article['url']}")
#         #     print(f"Image: {article['main_image_url']}")
#         #     # print(f"Text: {article['article_text'][:200]}...")
#         #     if not article['article_text']:
#         #         print("WARN: Article text is empty!")
#     else:
#         print(f"\nFailed to collect articles from NPR - {test_category_path}.")

# if __name__ == '__main__':
#    asyncio.run(main_test())
