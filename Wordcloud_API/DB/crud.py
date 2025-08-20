from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from . import models
from typing import List, Dict, Any
from datetime import datetime

def clear_and_save_trend_keywords(db: Session, keywords_data: List[Dict[str, Any]]) -> List[models.TrendKeyword]:
    db.query(models.TrendKeyword).delete()
    
    db_keywords = []
    current_time = datetime.now()
    
    for data in keywords_data:
        db_keyword = models.TrendKeyword(
            word=data.get('word', data.get('keyword', '')),
            score=data.get('score', data.get('search_volume', 0)),
            created_at=current_time,
            updated_at=current_time
        )
        db_keywords.append(db_keyword)
    
    db.bulk_save_objects(db_keywords)
    db.commit()
    return db_keywords 

def get_trend_keyword_words(db: Session) -> List[str]:
    """
    데이터베이스에서 모든 트렌드 키워드를 조회하여 word만 리스트로 반환
    """
    return [keyword.word for keyword in db.query(models.TrendKeyword).all()] 