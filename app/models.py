# In app/models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    analyses = relationship("Analysis", back_populates="owner")

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    assessment = Column(Text)
    key_info_json = Column(Text) # Storing JSON as a string
    actions_json = Column(Text) # Storing JSON as a string
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="analyses")

class AnalysisMeta(Base):
    __tablename__ = "analysis_meta"
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(String, nullable=True)
    extracted_text_json = Column(Text, nullable=True)
    page_images_json = Column(Text, nullable=True)
    risk_level = Column(String, nullable=True)
    risk_reason = Column(Text, nullable=True)
    content_hash = Column(String, index=True, nullable=True)
    conversation_json = Column(Text, nullable=True)

class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), index=True, nullable=False)
    date = Column(String, nullable=False)
    label = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    description = Column(Text, nullable=False)