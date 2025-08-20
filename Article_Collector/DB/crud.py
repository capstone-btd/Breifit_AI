from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from . import models
from typing import List, Dict, Any
from datetime import datetime

def get_or_create(db: Session, model, defaults=None, **kwargs):
    """
    주어진 조건으로 객체를 조회하고, 없으면 새로 생성합니다.
    """
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        params = {**kwargs, **(defaults or {})}
        instance = model(**params)
        try:
            db.add(instance)
            db.commit()
            db.refresh(instance)
            return instance, True
        except IntegrityError:
            db.rollback()
            instance = db.query(model).filter_by(**kwargs).first()
            return instance, False

def get_article_by_url(db: Session, url: str):
    """
    기능: URL을 기반으로 ArticleSource 테이블에서 원본 기사를 찾아 연결된 Article 객체를 반환합니다. 기사 중복 여부를 체크하는 데 사용됩니다.
    input: db (DB 세션), url (검색할 기사의 원본 URL)
    output: 이미 존재하는 경우 Article 객체, 없으면 None
    """
    source = db.query(models.ArticleSource).filter(models.ArticleSource.url == url).first()
    if source:
        return source.article
    return None

def create_article(db: Session, article_data: Dict[str, Any]) -> models.Article:
    """
    기능: 하나의 대표 기사(Article) 객체를 생성하고, 연관된 Category, Image 정보도 함께 저장합니다.
    input: db (DB 세션), article_data (기사 정보를 담은 딕셔너리)
    output: 생성된 Article 객체 또는 실패 시 None
    """
    if not all(k in article_data for k in ['title', 'body', 'category']):
        print(f"오류: 대표 기사 생성에 필수 필드가 누락되었습니다: {article_data}")
        return None

    db_article = models.Article(
        title=article_data['title'],
        body=article_data['body'],
        created_at=datetime.now()
    )
    db.add(db_article)
    db.flush()

    db_category = models.ArticleCategory(article_id=db_article.id, category=article_data['category'])
    db.add(db_category)

    # image_url이 존재하고 비어있지 않은 경우에만 ArticleImage를 생성합니다.
    if article_data.get('image_url'):
        db_image = models.ArticleImage(article_id=db_article.id, image_url=article_data['image_url'])
        db.add(db_image)
    
    print(f"Article 생성 완료 (ID: {db_article.id}, 제목: {db_article.title[:20]}...)")
    return db_article

def create_article_sources_in_batch(db: Session, sources_data: List[Dict[str, Any]]):
    """
    기능: 여러 개의 원본 기사 출처(ArticleSource) 정보를 배치(batch) 형태로 한 번에 저장합니다.
    input: db (DB 세션), sources_data (여러 출처 정보를 담은 딕셔너리의 리스트)
    output: 없음
    """
    db_sources = []
    for source_data in sources_data:
        existing_source = db.query(models.ArticleSource).filter(models.ArticleSource.url == source_data['url']).first()
        if existing_source:
            print(f"경고: 이미 존재하는 URL이므로 ArticleSource 생성을 건너뜁니다: {source_data['url']}")
            continue

        db_sources.append(models.ArticleSource(**source_data))
    
    if db_sources:
        db.bulk_save_objects(db_sources)
        print(f"{len(db_sources)}개의 ArticleSource 정보 배치 저장 완료.")

def create_single_article(db: Session, article_data: Dict[str, Any]) -> models.Article | None:
    """
    기능: 요약된 단일 기사(Noise)와 그 출처 정보를 DB에 한 번에 저장합니다. 모든 과정은 하나의 트랜잭션으로 처리됩니다.
    input: db (DB 세션), article_data (요약된 기사와 원본 출처 정보를 모두 포함한 딕셔너리)
    output: 성공적으로 생성된 Article 객체 또는 실패 시 None
    """
    if get_article_by_url(db, article_data['source_url']):
        print(f"경고: 이미 DB에 존재하는 기사입니다. 건너뜁니다. URL: {article_data['source_url']}")
        return None
        
    try:
        db_article = create_article(db, article_data)
        if not db_article:
            raise ValueError("대표 기사 생성에 실패했습니다.")
        
        source_data = {
            'article_id': db_article.id,
            'title': article_data['source_title'],
            'url': article_data['source_url'],
            'press_company': article_data['press_company']
        }
        db_source = models.ArticleSource(**source_data)
        db.add(db_source)
        
        db.commit()
        print(f"단일 기사 및 Source 저장 완료 (Article ID: {db_article.id})")
        return db_article
    except Exception as e:
        print(f"오류: 단일 기사 저장 중 롤백합니다. {e}")
        db.rollback()
        return None

def create_grouped_article(db: Session, representative_article_data: Dict[str, Any], source_articles_data: List[Dict[str, Any]]) -> models.Article | None:
    """
    기능: 요약된 그룹 기사와 그룹에 속한 모든 원본 기사들의 출처 정보를 DB에 한 번에 저장합니다. 모든 과정은 하나의 트랜잭션으로 처리됩니다.
    input: db (DB 세션), representative_article_data (대표 기사 정보), source_articles_data (모든 원본 기사 출처 정보 리스트)
    output: 성공적으로 생성된 Article 객체 또는 실패 시 None
    """
    main_source_url = source_articles_data[0]['url']
    if get_article_by_url(db, main_source_url):
        print(f"경고: 이미 DB에 존재하는 대표 기사입니다. 건너뜁니다. URL: {main_source_url}")
        return None

    try:
        db_article = create_article(db, representative_article_data)
        if not db_article:
             raise ValueError("대표 기사 생성에 실패했습니다.")

        for source_data in source_articles_data:
            source_data['article_id'] = db_article.id
        
        create_article_sources_in_batch(db, source_articles_data)

        db.commit()
        print(f"그룹 기사 및 Sources 저장 완료 (Article ID: {db_article.id})")
        return db_article
    except Exception as e:
        print(f"오류: 그룹 기사 저장 중 롤백합니다. {e}")
        db.rollback()
        return None