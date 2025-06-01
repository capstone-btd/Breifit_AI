from typing import List, Dict, Tuple

def summarize_and_extract_keywords(grouped_articles_data: List[Dict]) -> List[Dict]:
    """
    그룹화된 기사 묶음 또는 개별 기사 내용을 받아 요약하고 핵심 키워드를 추출합니다.

    Args:
        grouped_articles_data (List[Dict]): group_articles의 결과물.
                                           각 딕셔너리는 "group_id", "articles" 리스트 등을 포함.
                                           또는 요약할 단일 기사 텍스트를 가진 객체 리스트일 수도 있음.

    Returns:
        List[Dict]: 각 그룹/기사에 대한 요약 및 키워드 정보가 추가된 리스트.
                    예: [
                        {
                            "group_id": "unique_group_id_1", (또는 "article_id")
                            "original_data": { ... }, (선택적: 원본 그룹/기사 정보)
                            "summary": "AI가 생성한 요약문...",
                            "extracted_keywords": ["중요키워드A", "중요키워드B"]
                        },
                        ...
                    ]
    """
    print("문서 요약 및 키워드 추출 로직 실행...")
    processed_data = []

    for group_data in grouped_articles_data:
        group_id = group_data.get("group_id", "unknown_group")
        
        # 그룹 내 모든 기사 텍스트를 합치거나, 대표 기사 텍스트를 선택
        # 여기서는 간단히 첫 번째 기사의 텍스트를 사용한다고 가정
        # 실제로는 모든 텍스트를 취합하거나, 가장 중요한 기사를 선별하는 로직 필요
        text_to_summarize = ""
        if group_data.get("articles") and isinstance(group_data["articles"], list) and len(group_data["articles"]) > 0:
            # 그룹의 경우 여러 기사 텍스트를 취합하는 로직 필요
            # 여기서는 첫번째 기사의 텍스트를 임시로 사용
            first_article_in_group = group_data["articles"][0]
            text_to_summarize = first_article_in_group.get("article_text", "")
            if not text_to_summarize: # article_text가 없을 경우 title이라도.
                 text_to_summarize = first_article_in_group.get("title", "")
        elif group_data.get("article_text"): # 단일 기사 객체의 경우
            text_to_summarize = group_data["article_text"]
        
        if not text_to_summarize:
            print(f"경고: {group_id}에 대해 요약할 텍스트가 없습니다.")
            summary = "요약할 내용 없음."
            keywords = []
        else:
            # === 구현 예정: 실제 요약 및 키워드 추출 모델 연동 ===
            # 예: Hugging Face Transformers 라이브러리의 요약 모델 (BART, T5 등)
            # 예: KoBART (한국어 요약), KeyBERT 또는 TF-IDF 기반 키워드 추출
            summary = f"요약된 내용: {text_to_summarize[:100]}..." # 임시 요약
            keywords = [word for word in text_to_summarize.split()[:5] if len(word) > 3] # 임시 키워드

        processed_data.append({
            "group_id": group_id,
            "summary": summary,
            "extracted_keywords": keywords,
            "original_group_data": group_data # 원본 그룹 정보 포함 (선택적)
        })
        print(f"{group_id}에 대한 요약 및 키워드 추출 완료.")
        
    return processed_data 