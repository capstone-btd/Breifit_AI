from typing import List, Dict

def group_articles(articles: List[Dict]) -> List[Dict]:
    """
    주어진 기사 리스트를 내용 유사도 등을 기반으로 그룹화합니다.
    각 그룹은 같은 주제를 다루는 기사들의 묶음입니다.

    Args:
        articles (List[Dict]): 수집된 개별 기사 데이터 리스트.
                                각 딕셔너리는 'title', 'article_text', 'source', 'url' 등을 포함합니다.

    Returns:
        List[Dict]: 그룹화된 기사 리스트.
                    예: [
                        {
                            "group_id": "unique_group_id_1",
                            "representative_title": "대표 제목",
                            "keywords": ["키워드1", "키워드2"],
                            "articles": [
                                {"source": "cnn", "url": "...", "title": "..."},
                                {"source": "bbc", "url": "...", "title": "..."}
                            ]
                        },
                        ...
                    ]
    """
    print("기사 그룹화 로직 실행...")
    # === 구현 예정 ===
    # 1. 각 기사의 텍스트를 벡터로 변환 (예: TF-IDF, Sentence-BERT 등 사용)
    # 2. 벡터 간 유사도 계산 (예: 코사인 유사도)
    # 3. 유사도 임계값을 기준으로 클러스터링 알고리즘 적용 (예: DBSCAN, 계층적 클러스터링)
    #    또는 유사도가 높은 기사들을 순차적으로 묶어나가는 방식
    # 4. 각 그룹에 고유 ID 부여 및 대표 정보(제목, 키워드) 생성
    
    # 임시 반환: 모든 기사를 하나의 그룹으로 묶거나, 또는 원본 그대로 반환
    # 실제 구현에서는 정교한 그룹화 로직이 필요합니다.
    if not articles:
        return []

    # 예시: 단순히 첫 번째 기사 제목을 대표 제목으로 사용하고 모든 기사를 한 그룹으로 묶음
    # 이 부분은 실제 그룹핑 로직으로 대체되어야 합니다.
    grouped_data = [
        {
            "group_id": "temp_group_01",
            "representative_title": articles[0].get("title", "N/A") if articles else "N/A",
            "keywords": استخراج_키워드_예시(articles[0].get("article_text", "") if articles else ""), # 임시 키워드 추출 함수
            "articles": articles # 모든 기사를 이 그룹에 포함
        }
    ]
    print(f"{len(grouped_data)}개의 그룹으로 기사들을 그룹화했습니다. (임시 로직)")
    return grouped_data

# 임시 키워드 추출 함수 예시 (실제로는 더 정교한 NLP 라이브러리 사용)
def استخراج_키워드_예시(text: str, num_keywords: int = 5) -> List[str]:
    if not text:
        return []
    # 간단히 공백으로 단어 분리 후 빈도수 높은 단어 (불용어 처리 등 필요)
    words = [word.lower() for word in text.split() if len(word) > 3]
    if not words:
        return []
    from collections import Counter
    return [item[0] for item in Counter(words).most_common(num_keywords)] 