import re

def preprocess_text_simple(text: str) -> str:
    """
    텍스트에서 불필요한 공백, 특수문자, 이메일, URL, 저작권 문구 등을 제거합니다.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. 이스케이프된 개행/탭 문자와 실제 공백/줄바꿈을 단일 공백으로 치환
    text = re.sub(r'\\n|\\t|\\r|\s+', ' ', text).strip()
    
    # 2. 괄호와 그 안의 내용 제거
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    
    # 3. 이메일과 URL 제거
    text = re.sub(r'[\w\.-]+@[\w\.-]+', '', text)
    text = re.sub(r'https?://\S+', '', text)
    
    # 4. 저작권 관련 문구 제거
    copyright_pattern = r'(저작권자|copyright|ⓒ|©)\s?\(?c\)?\s?\w*|무단\s?(전재|배포|재배포)\s?금지|AI\s?학습\s?및\s?활용\s?금지|All\s?rights\s?reserved'
    text = re.sub(copyright_pattern, '', text, flags=re.IGNORECASE)
    
    # 5. 날짜/시간 '송고' 문구 제거
    text = re.sub(r'\d{4}[/\.]\d{2}[/\.]\d{2}\s\d{2}:\d{2}\s송고', '', text)
    
    # 6. 허용된 문자 외 모든 문자 제거
    text = re.sub(r"[^A-Za-z0-9가-힣\s\.,\'\"%·-]", '', text)
    
    # 7. 여분의 공백 정리
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text 