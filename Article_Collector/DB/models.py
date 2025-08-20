from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Article(Base):
    __tablename__ = 'article'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    categories = relationship("ArticleCategory", back_populates="article")
    images = relationship("ArticleImage", back_populates="article")
    sources = relationship("ArticleSource", back_populates="article")

class ArticleCategory(Base):
    __tablename__ = 'article_category'

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey('article.id'), nullable=False)
    category = Column(String(50), nullable=False)

    article = relationship("Article", back_populates="categories")

class ArticleImage(Base):
    __tablename__ = 'article_image'

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey('article.id'), nullable=False)
    image_url = Column(Text, nullable=False)

    article = relationship("Article", back_populates="images")

class ArticleSource(Base):
    __tablename__ = 'article_source'

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey('article.id'), nullable=False)
    title = Column(String(255), nullable=False)
    url = Column(String(255), nullable=False, unique=True)
    press_company = Column(String(50), nullable=False)

    article = relationship("Article", back_populates="sources") 