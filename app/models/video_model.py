from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.db.session import Base

class VideoModel(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    title = Column(String, index=True)
    file_name = Column(String, unique=True, index=True, nullable=True)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)