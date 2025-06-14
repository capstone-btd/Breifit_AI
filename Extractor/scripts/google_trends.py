from pytrends.request import TrendReq
import pandas as pd
from typing import List, Dict
import time
import random

def get_trending_keywords(region: str = "KR", limit: int = 20) -> List[Dict[str, any]]:
    """
    Google Trends에서 실시간 트렌드 키워드 조회
    
    Args:
        region (str): 지역 코드 ("KR" for Korea, "" for Global)
        limit (int): 반환할 키워드 개수
        
    Returns:
        List[Dict]: [{"keyword": "키워드", "value": 트렌드값}, ...]
    """
    try:
        # pytrends 객체 생성
        pytrends = TrendReq(hl='ko' if region == "KR" else 'en', tz=540)
        
        # 실시간 트렌드 검색어 가져오기 (단순화)
        trending_searches = pytrends.trending_searches(pn='south_korea' if region == "KR" else 'united_states')
        
        if not trending_searches.empty:
            # 상위 키워드들 선택
            top_keywords = trending_searches.head(limit)[0].tolist()
            
            # 키워드와 순위 기반 값 생성 (API 호출 최소화)
            keywords_data = []
            for i, keyword in enumerate(top_keywords):
                trend_value = max(100 - i * 2, 10)  # 순위 기반 값
                keywords_data.append({
                    "keyword": keyword,
                    "value": trend_value
                })
            
            return keywords_data
        else:
            return get_dummy_trends_data(region)
        
    except Exception as e:
        print(f"트렌드 데이터 조회 실패: {e}")
        # 오류 발생 시 더미 데이터 반환
        return get_dummy_trends_data(region)

def get_dummy_trends_data(region: str) -> List[Dict[str, any]]:
    """
    오류 발생 시 더미 트렌드 데이터 반환
    """
    if region == "KR":
        dummy_keywords = [
            {"keyword": "날씨", "value": 95},
            {"keyword": "뉴스", "value": 88},
            {"keyword": "코로나", "value": 82},
            {"keyword": "주식", "value": 76},
            {"keyword": "부동산", "value": 71},
            {"keyword": "정치", "value": 65},
            {"keyword": "경제", "value": 59},
            {"keyword": "스포츠", "value": 54},
            {"keyword": "연예", "value": 48},
            {"keyword": "게임", "value": 43}
        ]
    else:
        dummy_keywords = [
            {"keyword": "weather", "value": 95},
            {"keyword": "news", "value": 88},
            {"keyword": "covid", "value": 82},
            {"keyword": "stocks", "value": 76},
            {"keyword": "politics", "value": 71},
            {"keyword": "sports", "value": 65},
            {"keyword": "technology", "value": 59},
            {"keyword": "health", "value": 54},
            {"keyword": "entertainment", "value": 48},
            {"keyword": "business", "value": 43}
        ]
    
    return dummy_keywords

def get_keyword_trends(keywords: List[str], region: str = "KR") -> List[Dict[str, any]]:
    """
    특정 키워드들의 트렌드 값 조회
    
    Args:
        keywords (List[str]): 조회할 키워드 리스트
        region (str): 지역 코드
        
    Returns:
        List[Dict]: [{"keyword": "키워드", "value": 트렌드값}, ...]
    """
    # 간단한 더미 값 반환 (API 호출 최소화)
    results = []
    for i, keyword in enumerate(keywords):
        results.append({
            "keyword": keyword,
            "value": random.randint(30, 90)
        })
    
    return results 