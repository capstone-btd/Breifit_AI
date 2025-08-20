import re

PATTERNS = {
    "bracket": re.compile(r'\([^)]*\)|\[[^\]]*\]'),
    "url_email": re.compile(r'(https?|ftp)://[^\s/$.?#].[^\s]*|[\w\.-]+@[\w\.-]+'),
    "boilerplate": re.compile(
        r'\b[가-힣a-zA-Z]{2,5}\s?(기자|특파원|인턴기자|논설위원|연구원|객원기자)\b|'
        r'([\(<\[]?\s*(사진|자료|제공)\s*[:=]\s*[\w\s,]+[\]>\)]?)|'
        r'(저작권자|copyright|ⓒ|©)\s?\(?c\)?\s?[\w\s\.]+|'
        r'무단\s?(전재|배포|재배포|복제)\s?금지|'
        r'AI\s?학습\s?및\s?활용\s?금지|'
        r'All\s?rights\s?reserved|'
        r'\(끝\)|'
        r'[\w\s]+(뉴스|신문|일보|미디어|방송)$'
    ),
    "symbols": re.compile(r'[=\*#◇◆■▶▲▷▼▽◀◁▣◎→]'),
    "special_chars": re.compile(r'ㆍ|·|…'),
    "whitespace": re.compile(r'[ \t\r\f\v]+'),
    "multi_newline": re.compile(r'\n{3,}')
}

def clean_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""

    text = text.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
    
    text = PATTERNS["bracket"].sub('', text)
    text = PATTERNS["url_email"].sub('', text)
    text = PATTERNS["boilerplate"].sub('', text)
    text = PATTERNS["symbols"].sub(' ', text)
    
    # 순차적 치환이 더 안정적인 경우
    text = text.replace('ㆍ', ' ').replace('·', ' ').replace('…', '...')
    
    text = PATTERNS["whitespace"].sub(' ', text)
    text = PATTERNS["multi_newline"].sub('\n\n', text)
    
    return text.strip()

def preprocess_text_simple(text: str) -> str:
    return clean_text(text)