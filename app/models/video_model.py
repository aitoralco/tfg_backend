from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class VideoModel(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, index=True)
    file_name = Column(String, unique=True, index=True, nullable=True)
    shared = Column(Boolean, default=False)
    status_id = Column(
        Integer, ForeignKey("video_status.id"), nullable=False, default=1
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con los status
    status = relationship("VideoStatusModel", back_populates="videos")

    # Relación con los videos
    user = relationship("UserModel", back_populates="videos")
