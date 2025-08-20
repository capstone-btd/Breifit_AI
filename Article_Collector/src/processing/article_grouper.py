import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from typing import List, Dict, Any, Tuple

# 한국어 처리를 위한 Okt 토크나이zer 시도
try:
    from konlpy.tag import Okt
    okt = Okt()
    print("Konlpy Okt 토크나이저 로드 완료.")
except Exception as e:
    okt = None
    print(f"경고: Konlpy Okt 토크나이저 초기화 실패. ({e})")
    print("      'pip install konlpy'와 Java(JDK) 설치 및 JAVA_HOME 환경변수 설정이 필요할 수 있습니다.")
    print("      한국어 군집화 시 기본 토크나이저로 계속 진행합니다.")

def korean_tokenizer(text: str) -> List[str]:
    """
    기능: Konlpy Okt 형태소 분석기를 사용하여 입력된 한국어 텍스트에서 명사만 추출하여 리스트로 반환합니다. Okt가 없으면 공백 기준으로 단어를 분리합니다.
    input: text (토큰화할 한국어 텍스트)
    output: 명사 토큰의 리스트
    """
    if okt is None:
        return text.split()
    return okt.nouns(text)

class ArticleGrouper:
    def __init__(self, eps=0.5, min_samples=2):
        """
        기능: ArticleGrouper 클래스의 인스턴스를 초기화합니다. DBSCAN 클러스터링 알고리즘을 설정합니다.
        input: eps (DBSCAN의 eps 파라미터), min_samples (클러스터를 구성하는 최소 샘플 수)
        output: 없음
        """
        self.dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
        print("ArticleGrouper 초기화 완료.")

    def group(self, articles: List[Dict[str, Any]]) -> Tuple[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
        """
        기능: TF-IDF와 DBSCAN 알고리즘을 사용하여 기사 리스트를 내용이 유사한 그룹과 그렇지 않은 단일 기사(노이즈)로 분류
        input: articles (처리할 기사 딕셔너리의 리스트)
        output: (groups, noise) 튜플. groups는 유사 기사 묶음(리스트의 리스트)이고, noise는 그룹에 속하지 않는 단일 기사들의 리스트
        """
        if len(articles) < 2:
            print("기사가 2개 미만이라 그룹핑을 건너뛰고 모든 기사를 노이즈로 처리합니다.")
            return [], articles

        bodies = [article.get('body', article.get('title', '')) for article in articles]

        # 언어 감지 (첫 번째 기사 기준)
        is_korean = any('\uac00' <= char <= '\ud7a3' for char in bodies[0])
        print(f"언어 감지 결과: 한국어={is_korean}")

        if is_korean and okt:
            vectorizer = TfidfVectorizer(tokenizer=korean_tokenizer, token_pattern=None, min_df=3, max_df=0.4)
        else:
            vectorizer = TfidfVectorizer(stop_words='english', min_df=3, max_df=0.4)
        
        try:
            tfidf_matrix = vectorizer.fit_transform(bodies)
        except ValueError as e:
            print(f"TF-IDF 벡터화 오류: {e}. 모든 기사를 노이즈로 처리합니다.")
            return [], articles

        if tfidf_matrix.shape[0] == 0:
            print("유의미한 단어가 없어 군집화를 건너뛰고 모든 기사를 노이즈로 처리합니다.")
            return [], articles

        clusters = self.dbscan.fit_predict(tfidf_matrix)

        groups = []
        noise = []
        
        # 결과를 그룹과 노이즈로 분리
        grouped_indices = {}
        for i, cluster_id in enumerate(clusters):
            if cluster_id == -1:
                noise.append(articles[i])
            else:
                if cluster_id not in grouped_indices:
                    grouped_indices[cluster_id] = []
                grouped_indices[cluster_id].append(articles[i])
        
        for cluster_id in sorted(grouped_indices.keys()):
            groups.append(grouped_indices[cluster_id])

        print(f"군집화 완료: {len(groups)}개 그룹, {len(noise)}개 노이즈.")
        return groups, noise

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
    if not articles:
        return []
    grouped_data = [
        {
            "group_id": "temp_group_01",
            "representative_title": articles[0].get("title", "N/A") if articles else "N/A",
            "keywords": extract_keywords_example(articles[0].get("article_text", "") if articles else ""), # 임시 키워드 추출 함수
            "articles": articles # 모든 기사를 이 그룹에 포함
        }
    ]
    print(f"{len(grouped_data)}개의 그룹으로 기사들을 그룹화했습니다. (임시 로직)")
    return grouped_data

# 임시 키워드 추출 함수 예시 (실제로는 더 정교한 NLP 라이브러리 사용)
def extract_keywords_example(text: str, num_keywords: int = 5) -> List[str]:
    if not text:
        return []
    # 간단히 공백으로 단어 분리 후 빈도수 높은 단어 (불용어 처리 등 필요)
    words = [word.lower() for word in text.split() if len(word) > 3]
    if not words:
        return []
    from collections import Counter
    return [item[0] for item in Counter(words).most_common(num_keywords)] 