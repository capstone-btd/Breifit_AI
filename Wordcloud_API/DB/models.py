from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class TrendKeyword(Base):
    __tablename__ = 'wordcloud'

    id = Column(Integer, primary_key=True, index=True)
    score = Column(Integer, nullable=False)
    word = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()) 